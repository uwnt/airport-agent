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

    def make_chat():
        return ChatSession(
            client=FakeModel(),
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
    assert "- Cost: $0.0022" in region_switch
    assert "/home/" not in region_switch and "<local path>" in region_switch

    readme = (out / "README.md").read_text(encoding="utf-8")
    assert readme.count("| [") == len(script.CONVERSATIONS)
    assert "Average cost per question: $0.0022" in readme


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
    assert "Cost: unknown" in text
    assert "(1 failed)" in (out / "README.md").read_text(encoding="utf-8")


def test_prices_change_on_the_announced_day():
    script = load_script()
    usage = {"total_input_tokens": 1_000_000, "total_thought_tokens": 1_000_000}
    assert script.cost_usd("gemini-3.8-flash", usage, datetime.date(2026, 12, 31)) == 4.5
    assert script.cost_usd("gemini-3.8-flash", usage, datetime.date(2027, 1, 1)) == 9.0
    assert script.cost_usd("gemini-3.1-pro-preview", usage, DAY) == 14.0
    assert script.cost_usd("other", usage, DAY) is None
