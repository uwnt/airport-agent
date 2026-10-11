"""The tool loop with a fake model: no network and no key."""

import json
import re
from pathlib import Path

import pytest

from airport_agent.llm import SYSTEM_PROMPT, ChatSession, Settings, settings_from_env

SRC = Path(__file__).resolve().parents[1] / "src"


def call(name, args, call_id):
    return {"type": "function_call", "id": call_id, "name": name, "arguments": args}


def text(reply):
    return {"type": "model_output", "content": [{"type": "text", "text": reply}]}


class FakeModel:
    """Plays back scripted turns and keeps a copy of the history it was sent each time."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.seen = []

    def next_steps(self, history, tools, system_prompt):
        self.seen.append(json.loads(json.dumps(history)))
        return self.turns.pop(0)


def fake_tool(name, args):
    return {"tool": name, "args": args, "value": 42}


def session(model, max_tool_calls=8):
    return ChatSession(
        client=model,
        settings=Settings("fake", 100, max_tool_calls, 1),
        tools=[],
        run_tool=fake_tool,
    )


def test_tool_results_go_back_to_the_model_then_it_answers():
    model = FakeModel([call("rank_airports", {"region": "New England"}, "c1")], [text("BOS.")])
    answer = session(model).send("New England?")
    assert answer.text == "BOS."
    assert [(c.name, c.args) for c in answer.tool_calls] == [
        ("rank_airports", {"region": "New England"})
    ]
    result_step = model.seen[1][-1]
    assert result_step["type"] == "function_result" and result_step["call_id"] == "c1"
    assert json.loads(result_step["result"][0]["text"])["value"] == 42


def test_several_calls_in_one_turn_are_all_answered():
    model = FakeModel(
        [
            call("airport_profile", {"code": "LAX"}, "a"),
            call("airport_profile", {"code": "SNA"}, "b"),
        ],
        [text("done")],
    )
    answer = session(model).send("LAX vs SNA")
    assert [c.args["code"] for c in answer.tool_calls] == ["LAX", "SNA"]
    assert [s["call_id"] for s in model.seen[1] if s["type"] == "function_result"] == ["a", "b"]


def test_stops_after_max_tool_calls_with_a_plain_message():
    looping = [[call("demand_pressure", {"code": "SFO"}, f"c{i}")] for i in range(5)]
    chat = session(FakeModel(*looping), max_tool_calls=3)
    answer = chat.send("SFO?")
    assert answer.stopped_at_limit is True
    assert len(answer.tool_calls) == 3
    assert "stopped after 3 tool calls" in answer.text
    # Every call the model made has a result, so the history stays valid for the next question.
    calls = [s["id"] for s in chat.history if s["type"] == "function_call"]
    results = [s["call_id"] for s in chat.history if s["type"] == "function_result"]
    assert calls == results


def test_history_is_kept_for_a_follow_up_and_reset_clears_it():
    model = FakeModel([text("New England answer")], [text("Hartford answer")], [text("fresh")])
    chat = session(model)
    chat.send("New England candidates?")
    chat.send("and what about Hartford?")
    second = model.seen[1]
    user_texts = [s["content"][0]["text"] for s in second if s["type"] == "user_input"]
    assert user_texts == ["New England candidates?", "and what about Hartford?"]
    assert any(s["type"] == "model_output" for s in second)
    chat.reset()
    chat.send("hi")
    assert len(model.seen[2]) == 1


def test_a_failed_model_call_leaves_the_history_as_it_was():
    class Broken:
        def next_steps(self, *args):
            raise TimeoutError("slow")

    chat = session(Broken())
    with pytest.raises(TimeoutError):
        chat.send("hello")
    assert chat.history == []


def test_settings_from_env_defaults_and_overrides():
    defaults = settings_from_env({})
    assert defaults.model.startswith("gemini-") and defaults.max_tool_calls > 0
    custom = settings_from_env({"GEMINI_MODEL": "m", "MAX_TOOL_CALLS": "2"})
    assert (custom.model, custom.max_tool_calls) == ("m", 2)


def test_system_prompt_states_the_rules():
    for rule in (
        "must appear in a tool result",
        "general knowledge",
        "verified_facts",
        "Assumptions and data",
        "not investment advice",
        "out of scope",
        "Otherwise don't mention scope",
    ):
        assert rule in SYSTEM_PROMPT, rule


def test_only_llm_imports_the_google_sdk():
    importers = [
        path.name
        for path in SRC.rglob("*.py")
        if re.search(
            r"^\s*(from google import genai|import google\.genai|from google\.genai)",
            path.read_text(encoding="utf-8"),
            re.M,
        )
    ]
    assert importers == ["llm.py"]


def test_a_spent_quota_fails_at_once_instead_of_waiting_for_retry_after(monkeypatch):
    # Google answers a spent daily quota with 429 and a Retry-After of hours; the SDK would
    # sleep that long. Only short-lived server errors are retried.
    from airport_agent import llm

    seen = {}
    monkeypatch.setattr(llm.genai, "Client", lambda **kwargs: seen.update(kwargs))
    llm.GeminiClient(settings_from_env({}))
    retry = seen["http_options"].retry_options
    assert 429 not in retry.http_status_codes
    assert 503 in retry.http_status_codes and retry.attempts > 1


# --- Streaming: steps reported as they happen ------------------------------------------------


def test_listener_hears_tool_steps_and_text_in_order():
    def answer(on_text):
        on_text("BOS ")
        on_text("leads.")
        return [text("BOS leads.")]

    class StreamingModel(FakeModel):
        def next_steps(self, history, tools, system_prompt, on_text=None):
            turn = super().next_steps(history, tools, system_prompt)
            return turn(on_text) if callable(turn) else turn

    heard = []
    model = StreamingModel([call("rank_airports", {"region": "New England"}, "c1")], answer)
    reply = session(model).send("New England?", on_event=lambda k, d: heard.append((k, d)))
    assert reply.text == "BOS leads."
    assert heard == [
        ("tool_start", {"name": "rank_airports", "args": {"region": "New England"}}),
        (
            "tool_result",
            {
                "name": "rank_airports",
                "args": {"region": "New England"},
                "result": fake_tool("rank_airports", {"region": "New England"}),
            },
        ),
        ("text", {"text": "BOS "}),
        ("text", {"text": "leads."}),
    ]


def test_streamed_events_are_joined_into_the_same_steps():
    from airport_agent.llm import assemble_steps

    events = [
        {"event_type": "interaction.created", "interaction": {"id": "x"}},
        {"event_type": "step.start", "index": 0, "step": {"type": "thought"}},
        {
            "event_type": "step.delta",
            "index": 0,
            "delta": {"type": "thought_signature", "signature": "sig"},
        },
        {"event_type": "step.stop", "index": 0},
        {"event_type": "step.start", "index": 1, "step": {"type": "model_output"}},
        {"event_type": "step.delta", "index": 1, "delta": {"type": "text", "text": "Let me "}},
        {"event_type": "step.delta", "index": 1, "delta": {"type": "text", "text": "check."}},
        {"event_type": "step.stop", "index": 1},
        {
            "event_type": "step.start",
            "index": 2,
            "step": {"type": "function_call", "id": "c1", "name": "rank_airports", "arguments": {}},
        },
        {
            "event_type": "step.delta",
            "index": 2,
            "delta": {"type": "arguments_delta", "arguments": '{"region": "New '},
        },
        {
            "event_type": "step.delta",
            "index": 2,
            "delta": {"type": "arguments_delta", "arguments": 'England"}'},
        },
        {"event_type": "step.stop", "index": 2},
        {"event_type": "interaction.completed", "interaction": {"status": "requires_action"}},
    ]
    pieces = []
    assert assemble_steps(events, pieces.append) == [
        {"type": "thought", "signature": "sig"},
        text("Let me check."),
        call("rank_airports", {"region": "New England"}, "c1"),
    ]
    assert pieces == ["Let me ", "check."]


def test_stream_error_event_raises():
    from airport_agent.llm import ModelError, assemble_steps

    events = [{"event_type": "error", "error": {"message": "Deadline expired", "code": "x"}}]
    with pytest.raises(ModelError, match="Deadline expired"):
        assemble_steps(events, print)


def test_client_streams_only_when_someone_listens():
    from airport_agent.llm import GeminiClient

    class Event:
        def __init__(self, data):
            self.data = data

        def model_dump(self, **kwargs):
            return self.data

    class Interactions:
        def __init__(self):
            self.requests = []

        def create(self, **request):
            self.requests.append(request)
            return [
                Event({"event_type": "step.start", "index": 0, "step": {"type": "model_output"}}),
                Event(
                    {
                        "event_type": "step.delta",
                        "index": 0,
                        "delta": {"type": "text", "text": "Hi"},
                    }
                ),
            ]

    client = GeminiClient.__new__(GeminiClient)
    client.settings = Settings("fake-model", 100, 8, 1)
    client.client = type("Fake", (), {"interactions": Interactions()})()
    pieces = []
    assert client.next_steps([], [], "prompt", on_text=pieces.append) == [text("Hi")]
    assert pieces == ["Hi"]
    assert client.client.interactions.requests[0]["stream"] is True
    assert client.client.interactions.requests[0]["store"] is False


def test_history_from_turns_keeps_only_text_turns():
    from airport_agent.llm import history_from_turns

    turns = [
        {"role": "user", "text": "Rank New England."},
        {"role": "model", "text": "BOS leads."},
        {"role": "system", "text": "ignored"},
        {"role": "user", "text": ""},
    ]
    assert history_from_turns(turns) == [
        {"type": "user_input", "content": [{"type": "text", "text": "Rank New England."}]},
        text("BOS leads."),
    ]


# --- Token usage ------------------------------------------------------------------------------


def test_usage_of_every_model_call_is_added_up_into_the_answer():
    class CountingModel(FakeModel):
        def next_steps(self, history, tools, system_prompt):
            n = len(self.seen) + 1
            self.last_usage = {"total_input_tokens": 100 * n, "total_output_tokens": n}
            return super().next_steps(history, tools, system_prompt)

    model = CountingModel([call("rank_airports", {}, "c1")], [text("BOS.")])
    answer = session(model).send("Rank?")
    assert answer.usage == {"total_input_tokens": 300, "total_output_tokens": 3}


def test_a_model_that_reports_no_usage_gives_empty_usage():
    assert session(FakeModel([text("hi")])).send("hello").usage == {}


def test_usage_counts_keeps_only_the_whole_number_totals():
    from airport_agent.llm import add_usage, usage_counts

    raw = {
        "total_input_tokens": 10,
        "total_thought_tokens": 4,
        "input_tokens_by_modality": [{"modality": "text", "tokens": 10}],
        "total_output_tokens": None,
    }
    assert usage_counts(raw) == {"total_input_tokens": 10, "total_thought_tokens": 4}
    assert usage_counts(None) == {}
    assert add_usage({"total_input_tokens": 5}, raw) == {
        "total_input_tokens": 15,
        "total_thought_tokens": 4,
    }


def test_streamed_usage_comes_from_the_completed_event():
    from airport_agent.llm import assemble_steps

    events = [
        {"event_type": "step.start", "index": 0, "step": {"type": "model_output"}},
        {"event_type": "step.delta", "index": 0, "delta": {"type": "text", "text": "Hi"}},
        {
            "event_type": "interaction.completed",
            "interaction": {
                "status": "completed",
                "usage": {"total_input_tokens": 7, "total_output_tokens": 2, "total_tokens": 9},
            },
        },
    ]
    usage = {}
    assert assemble_steps(events, lambda piece: None, usage=usage) == [text("Hi")]
    assert usage == {"total_input_tokens": 7, "total_output_tokens": 2, "total_tokens": 9}


def test_client_keeps_the_last_calls_usage_streamed_or_not():
    from airport_agent.llm import GeminiClient

    class Dumpable:
        def __init__(self, data):
            self.data = data

        def model_dump(self, **kwargs):
            return self.data

    class Interactions:
        def create(self, stream=False, **request):
            if stream:
                return [
                    Dumpable(
                        {
                            "event_type": "interaction.completed",
                            "interaction": {"usage": {"total_output_tokens": 3}},
                        }
                    )
                ]
            return Dumpable({"steps": [text("Hi")], "usage": {"total_input_tokens": 11}})

    client = GeminiClient.__new__(GeminiClient)
    client.settings = Settings("fake-model", 100, 8, 1)
    client.client = type("Fake", (), {"interactions": Interactions()})()
    assert client.next_steps([], [], "prompt") == [text("Hi")]
    assert client.last_usage == {"total_input_tokens": 11}
    client.next_steps([], [], "prompt", on_text=lambda piece: None)
    assert client.last_usage == {"total_output_tokens": 3}
