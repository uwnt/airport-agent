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
