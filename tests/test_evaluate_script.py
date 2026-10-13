"""The evaluation script with a fake model: no network, no key; it must write the files."""

import datetime
import importlib.util
from pathlib import Path

from airport_agent.llm import ChatSession, Settings

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate.py"
DAY = datetime.date(2026, 10, 11)


def load_script():
    spec = importlib.util.spec_from_file_location("evaluate_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeModel:
    """Calls one tool, then answers with one number from it and one it made up."""

    def __init__(self):
        self.last_usage = {}

    def next_steps(self, history, tools, system_prompt):
        self.last_usage = {"total_input_tokens": 1000, "total_output_tokens": 100}
        if history[-1]["type"] == "user_input":
            return [{"type": "function_call", "id": "c1", "name": "fake_tool", "arguments": {}}]
        return [{"type": "model_output", "content": [{"type": "text", "text": "Score 55; 77%."}]}]


def fake_tool(name, args):
    return {"score": 55.0, "source": "/home/analyst/data/file.json"}


def test_writes_a_transcript_per_conversation_and_an_index(tmp_path):
    script = load_script()

    counted = []

    def count_tokens(text):  # stands in for the API's token counter
        counted.append(text)
        return 500

    def make_chat():
        return ChatSession(
            client=script.ToolResultMeter(FakeModel(), count_tokens),
            settings=Settings("gemini-3.8-flash", 100, 8, 1),
            tools=[],
            run_tool=fake_tool,
        )

    out = tmp_path / "flash"
    assert script.main(["--model", "gemini-3.8-flash", "--out", str(out)], make_chat, DAY) == 0
    names = {name for name, _ in script.CONVERSATIONS}
    assert {p.stem for p in out.glob("*.md")} == names | {"README"}

    region_switch = (out / "h-trap-region-switch.md").read_text(encoding="utf-8")
    assert region_switch.count("## Question") == 2
    assert "Now do the same for the LA area." in region_switch
    assert "`fake_tool`" in region_switch
    assert "Score 55; 77%." in region_switch
    assert "1 not found in tool results (need a look): 77%" in region_switch
    # Two model calls of 1,000 in and 100 out at $0.75 / $3.75 per million.
    assert "- Cost (reported): $0.0022" in region_switch
    # Question 1: the second call resends one tool result (500 tokens). Question 2: its first
    # call resends that one, its second call both: 1,500. So 2,500 and 3,500 tokens in.
    assert "- Tool-result input tokens (estimated): 500" in region_switch
    assert "- Tool-result input tokens (estimated): 1,500" in region_switch
    assert "- Cost (estimated with tool results): $0.0026" in region_switch
    assert "- Cost (estimated with tool results): $0.0034" in region_switch
    # Each distinct result text is counted once per chat, however often it is resent.
    assert len(counted) == len(script.CONVERSATIONS)
    assert "/home/" not in region_switch and "<local path>" in region_switch

    readme = (out / "README.md").read_text(encoding="utf-8")
    assert readme.count("| [") == len(script.CONVERSATIONS)
    assert "Average cost per question, reported: $0.0022" in readme
    # 6,000 tool-result tokens over 10 questions: 600 more input tokens per question on average.
    assert "Average cost per question, estimated with tool results: $0.0027" in readme


def test_a_failed_model_call_is_written_down_and_the_run_goes_on(tmp_path):
    script = load_script()

    class Broken:
        def next_steps(self, *args):
            raise TimeoutError("slow")

    def make_chat():
        return ChatSession(client=Broken(), settings=Settings("m", 100, 8, 1), tools=[])

    out = tmp_path / "x"
    script.main(
        ["--model", "unknown-model", "--out", str(out), "--only", "f-trap-nonsense-code"],
        make_chat,
        DAY,
    )
    text = (out / "f-trap-nonsense-code.md").read_text(encoding="utf-8")
    assert "The model call failed: TimeoutError: slow" in text
    assert "Cost (reported): unknown" in text
    assert "Cost (estimated with tool results): unknown" in text
    assert "(1 failed)" in (out / "README.md").read_text(encoding="utf-8")


def test_prices_change_on_the_announced_day():
    script = load_script()
    usage = {"total_input_tokens": 1_000_000, "total_thought_tokens": 1_000_000}
    assert script.cost_usd("gemini-3.8-flash", usage, datetime.date(2026, 12, 31)) == 4.5
    assert script.cost_usd("gemini-3.8-flash", usage, datetime.date(2027, 1, 1)) == 9.0
    assert script.cost_usd("gemini-3.1-pro-preview", usage, DAY) == 14.0
    assert script.cost_usd("other", usage, DAY) is None


def test_a_failing_token_count_keeps_the_answer_and_makes_the_estimate_unknown(tmp_path):
    script = load_script()

    def count_tokens(text):  # the API's counter hitting a rate limit
        raise RuntimeError("429 Too Many Requests")

    def make_chat():
        return ChatSession(
            client=script.ToolResultMeter(FakeModel(), count_tokens),
            settings=Settings("gemini-3.8-flash", 100, 8, 1),
            tools=[],
            run_tool=fake_tool,
        )

    out = tmp_path / "flash"
    args = ["--model", "gemini-3.8-flash", "--out", str(out), "--only", "h-trap-region-switch"]
    script.main(args, make_chat, DAY)
    text = (out / "h-trap-region-switch.md").read_text(encoding="utf-8")
    assert "The model call failed" not in text
    assert text.count("Score 55; 77%.") == 2
    assert "- Cost (reported): $0.0022" in text
    assert "- Tool-result input tokens (estimated): unknown" in text
    assert "- Cost (estimated with tool results): unknown" in text
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "Average cost per question, estimated with tool results: unknown" in readme


def check_chat_maker(answer_text="Score 55.", broken=False):
    class Model(FakeModel):
        def next_steps(self, history, tools, system_prompt):
            if broken:
                raise TimeoutError("slow")
            steps = super().next_steps(history, tools, system_prompt)
            if history[-1]["type"] != "user_input":
                steps = [
                    {"type": "model_output", "content": [{"type": "text", "text": answer_text}]}
                ]
            return steps

    return lambda: ChatSession(
        client=Model(), settings=Settings("m", 100, 8, 1), tools=[], run_tool=fake_tool
    )


def test_check_passes_when_every_conversation_is_clean(tmp_path, capsys):
    script = load_script()
    assert script.main(["--check"], check_chat_maker(), DAY) == 0
    out = capsys.readouterr().out
    assert out.count("PASS ") == len(script.CONVERSATIONS)
    assert "FAIL" not in out
    assert not list(tmp_path.iterdir())


def test_check_fails_naming_the_conversation_with_an_invented_number(capsys):
    script = load_script()
    assert script.main(["--check"], check_chat_maker("Score 55; 77%."), DAY) == 1
    out = capsys.readouterr().out
    assert "FAIL a-new-england" in out and "77" in out
    assert "0 of 9" in out


def test_check_fails_when_a_model_call_errors(capsys):
    script = load_script()
    assert (
        script.main(
            ["--check", "--only", "f-trap-nonsense-code"], check_chat_maker(broken=True), DAY
        )
        == 1
    )
    assert "FAIL f-trap-nonsense-code" in capsys.readouterr().out


def test_without_check_model_and_out_are_required():
    script = load_script()
    try:
        script.main(["--model", "m"], check_chat_maker(), DAY)
    except SystemExit as stop:
        assert stop.code == 2
    else:
        raise AssertionError("expected a usage error")


def test_check_with_no_matching_conversation_fails(capsys):
    # A mistyped --only must not turn the release check into "0 of 0 passed", exit 0.
    script = load_script()
    assert script.main(["--check", "--only", "no-such-name"], check_chat_maker(), DAY) == 1
    assert "FAIL no conversation matched" in capsys.readouterr().out
