"""The terminal chat: no-key mode prints tables; chat mode prints steps then the answer."""

from airport_agent import cli, tools
from airport_agent.llm import Answer, ToolCall


def scripted(*lines):
    queue = list(lines)

    def read(prompt):
        if not queue:
            raise EOFError
        return queue.pop(0)

    return read


def run_no_key(monkeypatch, sample_cache, *lines):
    original = tools.run_tool
    monkeypatch.setattr(
        tools, "run_tool", lambda name, args: original(name, args, cache_dir=sample_cache)
    )
    out = []
    assert cli.no_key_mode(read=scripted(*lines), out=out.append) == 0
    return "\n".join(out)


def test_no_key_fixed_question_prints_a_table_with_sources(monkeypatch, sample_cache):
    out = run_no_key(monkeypatch, sample_cache, "1", "/quit")
    assert "No GEMINI_API_KEY" in out
    assert "[rank_airports]" in out and "Preset: balanced" in out
    assert " BOS " in out and "Sources:" in out and "as of 2026 Q1" in out


def test_no_key_anchorage_question(monkeypatch, sample_cache):
    out = run_no_key(monkeypatch, sample_cache, "3")
    assert "% long-haul" in out and "OpenSky" in out


def test_no_key_picker(monkeypatch, sample_cache):
    out = run_no_key(monkeypatch, sample_cache, "6", "BOS,BDL", "growth-focused")
    assert "Preset: growth-focused" in out and "BDL" in out


def test_no_key_error_is_printed_plainly(monkeypatch, sample_cache):
    out = run_no_key(monkeypatch, sample_cache, "6", "Atlantis", "")
    assert "Error: Unknown region" in out


def test_main_without_a_key_uses_no_key_mode(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "no_key_mode", lambda: "no-key")
    assert cli.main() == "no-key"


class FakeSession:
    def __init__(self):
        self.sent, self.resets = [], 0

    def send(self, text):
        self.sent.append(text)
        call = ToolCall("rank_airports", {"region": "New England"}, {"rows": []})
        return Answer(f"answer to {text}", [call])

    def reset(self):
        self.resets += 1


def test_chat_mode_prints_steps_then_answer_and_handles_reset():
    session, out = FakeSession(), []
    cli.chat_mode(session, read=scripted("Q1", "/reset", "/quit", "never"), out=out.append)
    text = "\n".join(out)
    assert 'step: rank_airports({"region": "New England"})' in text
    assert text.index("step:") < text.index("agent> answer to Q1")
    assert session.sent == ["Q1"] and session.resets == 1


def test_no_key_change_over_time_question_prints_a_change_table():
    out = []
    assert cli.no_key_mode(read=scripted("5", "/quit"), out=out.append) == 0
    text = "\n".join(out)
    assert "[compare_over_time]" in text and "SFO" in text and "2019-12 -> latest-" in text
    assert "Change" in text and "Sources:" in text
