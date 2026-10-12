"""The chat page and POST /chat, with a fake model: no network and no key."""

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from airport_agent import cli, server
from airport_agent.data.regions import REGIONS
from airport_agent.data.store import FileStore
from airport_agent.llm import ChatSession, Settings

NEW_ENGLAND = cli.FIXED_QUESTIONS[0][0]
SOURCES = {
    "bts_enplanements": {"source": "BTS passenger boardings", "as_of": "2018"},
    "bts_ontime": {"source": "BTS On-Time Performance", "as_of": "Oct 2017 to Sep 2019"},
    "dot_fares": {"source": "DOT Table 1a", "as_of": "2017 Q2"},
}


@pytest.fixture
def store(tmp_path_factory, sample_cache, monkeypatch):
    """A store with a latest snapshot and a 2019-12 one, both copies of the sample data."""
    root = tmp_path_factory.mktemp("store")
    for version, as_of in [("latest-2026-10-11", "2026-10-11"), ("2019-12", "2019-12-31")]:
        shutil.copytree(sample_cache, root / version)
        manifest = {"version": version, "as_of": as_of, "sources": SOURCES}
        (root / version / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("DATA_STORE", f"file://{root}")
    monkeypatch.setattr(server, "data", server.DataVersion(FileStore(root), clock=lambda: 0.0))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return root


@pytest.fixture
def web(store):
    return TestClient(server.app)


def events(response):
    """The server-sent events of a response, as (event, data) pairs."""
    assert response.headers["content-type"].startswith("text/event-stream")
    found = []
    for block in response.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        found.append((fields["event"], json.loads(fields["data"])))
    return found


def kinds(found):
    return [kind for kind, _ in found]


class StreamingModel:
    """Plays back scripted turns; a turn is a list of steps, or a function(on_text) -> steps."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.seen = []

    def next_steps(self, history, tools, system_prompt, on_text=None):
        self.seen.append(json.loads(json.dumps(history)))
        turn = self.turns.pop(0)
        return turn(on_text) if callable(turn) else turn


def with_model(monkeypatch, model):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        server,
        "make_session",
        lambda run_tool: ChatSession(
            client=model, settings=Settings("fake", 100, 8, 1), tools=[], run_tool=run_tool
        ),
    )


def call(name, args):
    return {"type": "function_call", "id": "c1", "name": name, "arguments": args}


def streamed(*pieces):
    def turn(on_text):
        for piece in pieces:
            on_text(piece)
        return [{"type": "model_output", "content": [{"type": "text", "text": "".join(pieces)}]}]

    return turn


# --- The page --------------------------------------------------------------------------------


def test_page_is_served_with_a_strict_content_policy(web):
    response = web.get("/")
    assert response.status_code == 200
    assert "<title>Airport expansion agent</title>" in response.text
    assert "Decision support, not investment advice" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]


@pytest.mark.parametrize(
    "path", ["app.js", "app.css", "vendor/marked.umd.js", "vendor/purify.min.js"]
)
def test_static_assets_are_served(web, path):
    response = web.get(f"/static/{path}")
    assert response.status_code == 200
    assert response.content


def test_page_loads_no_third_party_files(web):
    page = web.get("/").text
    assert "http://" not in page and "https://" not in page


def test_markdown_is_always_sanitised(web):
    script = web.get("/static/app.js").text
    assert "DOMPurify.sanitize(marked.parse(" in script
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in script  # the sanitised render is the only way markup gets in


def test_region_choices_are_known_regions():
    assert all(name.lower() in REGIONS for name in server.REGION_CHOICES)


# --- /info: versions and freshness -----------------------------------------------------------


def test_info_lists_versions_and_the_choices(web):
    body = web.get("/info").json()
    assert body["versions"] == ["latest", "2019-12"]
    assert body["version"] == "latest-2026-10-11"
    assert body["model"] is False
    assert body["questions"] == [q for q, _ in cli.FIXED_QUESTIONS]
    assert "balanced" in body["presets"]
    assert body["stale_reference"] == date.today().isoformat()


def test_point_in_time_freshness_is_judged_at_the_snapshot_date(web):
    body = web.get("/info", params={"version": "2019-12"}).json()
    assert body["version"] == "2019-12" and body["stale_reference"] == "2019-12-31"
    stale = {s["name"]: s["stale"] for s in body["sources"]}
    # 18 months by default: Dec 2018 is 12 months old, Sep 2019 3, 2017 Q2 (June 2017) 30.
    # The committed FAA table (2014) is listed with every snapshot and is always stale.
    assert stale == {
        "bts_enplanements": False,
        "bts_ontime": False,
        "dot_fares": True,
        "faa_capacity": True,
    }


def test_unknown_version_is_refused(web):
    assert web.get("/info", params={"version": "1999-12"}).status_code == 404
    response = web.post("/chat", json={"message": NEW_ENGLAND, "version": "../etc"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "as_of, end",
    [
        ("2026-10-11", (2026, 10)),
        ("2026-10-04 to 2026-10-10", (2026, 10)),
        ("Aug 2025 to Jul 2026", (2026, 7)),
        ("2026 Q1", (2026, 3)),
        ("2023", (2023, 12)),
        ("unknown", None),
    ],
)
def test_period_end_reads_the_manifest_forms(as_of, end):
    assert server.period_end(as_of) == end


def test_stale_means_more_than_the_set_number_of_months():
    reference = date(2026, 10, 11)
    assert not server.is_stale("2025 Q2", reference, 18)  # June 2025: 16 months
    assert server.is_stale("2023", reference, 18)  # December 2023: 34 months
    assert not server.is_stale("no date", reference, 18)


# --- POST /chat with the model ---------------------------------------------------------------


def test_tool_using_answer_streams_steps_then_text_then_done(web, monkeypatch):
    model = StreamingModel(
        [call("rank_airports", {"region": "New England"})], streamed("BOS ", "leads.")
    )
    with_model(monkeypatch, model)
    found = events(web.post("/chat", json={"message": NEW_ENGLAND}))
    assert kinds(found) == ["tool_start", "tool_result", "text", "text", "done"]
    assert found[0][1] == {"name": "rank_airports", "args": {"region": "New England"}}
    assert found[1][1]["result"]["rows"][0]["code"]  # the tool's own JSON, for the visuals
    assert [d["text"] for k, d in found if k == "text"] == ["BOS ", "leads."]
    assert found[-1][1]["text"] == "BOS leads."


def test_history_from_the_page_goes_to_the_model(web, monkeypatch):
    model = StreamingModel(streamed("Hartford is BDL."))
    with_model(monkeypatch, model)
    history = [
        {"role": "user", "text": "Rank New England."},
        {"role": "model", "text": "BOS leads."},
    ]
    found = events(web.post("/chat", json={"message": "And Hartford?", "history": history}))
    assert kinds(found)[-1] == "done"
    sent = model.seen[0]
    assert [(s["type"], s["content"][0]["text"]) for s in sent] == [
        ("user_input", "Rank New England."),
        ("model_output", "BOS leads."),
        ("user_input", "And Hartford?"),
    ]


def test_model_failure_ends_with_an_error_event(web, monkeypatch):
    def broken(on_text):
        raise RuntimeError("quota spent")

    with_model(monkeypatch, StreamingModel(broken))
    found = events(web.post("/chat", json={"message": "Rank New England."}))
    assert kinds(found) == ["error"]
    assert "quota spent" in found[0][1]["message"]


def test_tool_failure_ends_with_an_error_event(web, monkeypatch):
    def broken_tool(name, args, cache_dir=None):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(server.tools, "run_tool", broken_tool)
    with_model(monkeypatch, StreamingModel([call("rank_airports", {"region": "New England"})]))
    found = events(web.post("/chat", json={"message": "Rank New England."}))
    assert kinds(found) == ["tool_start", "error"]
    assert "disk gone" in found[-1][1]["message"]


def test_tool_error_result_is_shown_and_the_model_still_answers(web, monkeypatch):
    model = StreamingModel([call("airport_profile", {"code": "ZZZ"})], streamed("Unknown code."))
    with_model(monkeypatch, model)
    found = events(web.post("/chat", json={"message": "Profile ZZZ"}))
    assert kinds(found) == ["tool_start", "tool_result", "text", "done"]
    assert "error" in found[1][1]["result"]


def test_tools_read_the_picked_data_version(web, monkeypatch):
    read = []

    def recording_tool(name, args, cache_dir=None):
        read.append((name, cache_dir.name if cache_dir else None))
        return {"error": "stop here"}

    monkeypatch.setattr(server.tools, "run_tool", recording_tool)
    rank = {"name": "rank_airports", "args": {"region": "New England"}}
    over_time = {"name": "compare_over_time", "args": {"code": "BOS"}}
    web.post("/chat", json={"calls": [rank], "version": "2019-12"})
    web.post("/chat", json={"calls": [rank]})
    web.post("/chat", json={"calls": [over_time], "version": "2019-12"})
    assert read == [
        ("rank_airports", "2019-12"),
        ("rank_airports", "latest-2026-10-11"),
        ("compare_over_time", None),  # it picks its two versions from the store itself
    ]


# --- POST /chat without a key ----------------------------------------------------------------


def test_no_key_suggested_question_runs_its_tools(web):
    found = events(web.post("/chat", json={"message": NEW_ENGLAND}))
    assert kinds(found) == ["tool_start", "tool_result", "done"]
    result = found[1][1]["result"]
    top = result["rows"][0]
    assert f"**{top['code']} {top['name']}** ranks first here" in found[-1][1]["text"]
    assert f"score of {top['score']:g}" in found[-1][1]["text"]


def test_no_key_free_form_question_is_refused_plainly(web):
    found = events(web.post("/chat", json={"message": "Which airport should I buy?"}))
    assert found == [("error", {"message": server.NO_KEY_MESSAGE})]


def test_picker_profile_shows_the_tool_result_as_a_table(web):
    found = events(
        web.post("/chat", json={"calls": [{"name": "airport_profile", "args": {"code": "BOS"}}]})
    )
    assert kinds(found) == ["tool_start", "tool_result", "done"]
    assert found[-1][1]["text"].startswith("```text\n[airport_profile]\nBOS ")


def test_picker_tool_error_ends_with_an_error_event(web):
    found = events(
        web.post("/chat", json={"calls": [{"name": "airport_profile", "args": {"code": "ZZZ"}}]})
    )
    assert kinds(found) == ["tool_start", "tool_result", "error"]


def test_empty_question_is_refused(web):
    assert web.post("/chat", json={"message": "  "}).status_code == 422


def test_the_page_keeps_its_history_within_the_server_limits():
    # The page trims its history to these numbers; if the server's limits drift below them, a
    # long conversation starts failing with 422 until the page is reloaded.
    script = (Path(server.__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    turns = int(re.search(r"const MAX_TURNS = (\d+);", script)[1])
    total = int(re.search(r"const MAX_HISTORY_CHARS = (\d+);", script)[1])
    answer = int(re.search(r"const MAX_TURN_CHARS = (\d+);", script)[1])
    history = [{"role": "user", "text": "x" * (total // turns)}] * turns
    server.ChatRequest(message="x", history=history)  # accepted, no ValidationError
    # The page keeps whole question-and-answer pairs, and the latest pair always fits.
    assert turns % 2 == 0
    assert server.MAX_QUESTION_CHARS + answer <= total
    longest = [
        {"role": "user", "text": "x" * server.MAX_QUESTION_CHARS},
        {"role": "model", "text": "x" * answer},
    ]
    server.ChatRequest(message="x", history=longest)


def test_a_question_over_the_size_limit_is_refused(web):
    too_long = "x" * (server.MAX_QUESTION_CHARS + 1)
    assert web.post("/chat", json={"message": too_long}).status_code == 422
    assert web.post("/chat", json={"message": too_long[:-1], "calls": [CALL]}).status_code == 200


def test_the_refusal_message_is_readable_in_the_422_body(web):
    body = web.post("/chat", json={"message": "x" * (server.MAX_QUESTION_CHARS + 1)}).json()
    assert isinstance(body["detail"], list)
    assert f"at most {server.MAX_QUESTION_CHARS} characters" in body["detail"][0]["msg"]
    turns = [
        {"role": "user", "text": "x" * server.MAX_HISTORY_CHARS},
        {"role": "model", "text": "y"},
    ]
    msg = web.post("/chat", json={"calls": [CALL], "history": turns}).json()["detail"][0]["msg"]
    assert msg.startswith("Value error, ")  # the page strips this prefix


def test_the_page_shows_the_messages_of_a_422_refusal():
    script = (Path(server.__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    assert "Array.isArray(problem.detail)" in script
    assert "problem.detail.map(" in script
    assert 'replace(/^Value error, /, "")' in script


def test_more_than_ten_earlier_turns_are_refused(web):
    turns = [{"role": "user", "text": "Hi"}, {"role": "model", "text": "Hello."}] * 6
    assert len(turns) == server.MAX_HISTORY_TURNS + 2
    reply = web.post("/chat", json={"calls": [CALL], "history": turns})
    assert reply.status_code == 422
    ok = web.post("/chat", json={"calls": [CALL], "history": turns[: server.MAX_HISTORY_TURNS]})
    assert ok.status_code == 200


def test_earlier_turns_over_the_total_size_are_refused_with_a_clear_message(web):
    each = server.MAX_HISTORY_CHARS // 4
    turns = [{"role": "user", "text": "x" * each}, {"role": "model", "text": "y" * each}] * 2
    ok = web.post("/chat", json={"calls": [CALL], "history": turns})
    assert ok.status_code == 200  # exactly at the limit
    turns[-1] = {"role": "model", "text": "y" * (each + 1)}
    reply = web.post("/chat", json={"calls": [CALL], "history": turns})
    assert reply.status_code == 422
    assert "at most 20000 are accepted" in json.dumps(reply.json())


CALL = {"name": "airport_profile", "args": {"code": "BOS"}}


def test_picker_arguments_are_size_limited():
    big = {"calls": [{"name": "airport_profile", "args": {"code": "A" * 5_000}}]}
    with pytest.raises(ValueError, match="under 1000 characters"):
        server.ChatRequest(**big)
    server.ChatRequest(calls=[{"name": "rank_airports", "args": {"region": "New England"}}])


def test_tables_scroll_by_keyboard_and_short_hint_is_set_from_script():
    # Answer tables that overflow get a tab stop and a name after sanitising, and the narrow-screen
    # hint comes from script, not from a ::placeholder rule browsers do not all honour.
    static = Path(server.__file__).parent / "static"
    script = (static / "app.js").read_text(encoding="utf-8")
    css = (static / "app.css").read_text(encoding="utf-8")
    assert script.index("DOMPurify.sanitize") < script.index("function markScrollers")
    assert "wrap.scrollWidth > wrap.clientWidth" in script and "scrolls sideways" in script
    assert (
        script.count("markScrollers(") >= 6
    )  # definition, done, fail, resize, panel open, panel resize
    # The "How I got this" tables are marked when the panel opens and on resize while it is open.
    assert 'how.addEventListener("toggle"' in script and "markScrollers(how)" in script
    assert "details.how[open]" in script and 'class: "table-wrap"' in script
    assert "if (view.how.open) markScrollers(view.how)" in script
    # A failure marks the tables only after the final draw, and stops stale frames.
    fail_body = script[
        script.index("const fail =") : script.index("try {", script.index("const fail ="))
    ]
    assert (
        fail_body.index("finished = true")
        < fail_body.index("draw()")
        < fail_body.index("markScrollers(")
    )
    assert "matchMedia" in script
    assert "::placeholder" not in css


# --- Daily cap on model questions (the public site) --------------------------------------------

FREE = "Which airport should I buy?"


@pytest.fixture(autouse=True)
def fresh_daily_cap(monkeypatch):
    """Every test starts with no cap set and a fresh count on a fixed UTC day."""
    monkeypatch.delenv("MAX_MODEL_QUESTIONS_PER_DAY", raising=False)
    monkeypatch.setattr(server, "daily_cap", server.DailyCap(clock=lambda: date(2026, 10, 12)))


def test_without_the_cap_set_model_questions_are_not_limited(web, monkeypatch):
    model = StreamingModel(*(streamed("Fine.") for _ in range(5)))
    with_model(monkeypatch, model)
    for _ in range(5):
        assert kinds(events(web.post("/chat", json={"message": FREE}))) == ["text", "done"]
    assert server.DailyCap().limit() is None


def test_over_the_cap_a_free_question_gets_the_message_not_the_model(web, monkeypatch):
    monkeypatch.setenv("MAX_MODEL_QUESTIONS_PER_DAY", "2")
    model = StreamingModel(streamed("one"), streamed("two"))
    with_model(monkeypatch, model)
    for _ in range(2):
        assert kinds(events(web.post("/chat", json={"message": FREE})))[-1] == "done"
    over = events(web.post("/chat", json={"message": FREE}))
    assert over == [("error", {"message": server.CAP_MESSAGE})]
    assert len(model.seen) == 2  # the third question never reached the model


def test_over_the_cap_suggested_questions_and_the_picker_still_run_tools(web, monkeypatch):
    monkeypatch.setenv("MAX_MODEL_QUESTIONS_PER_DAY", "0")
    model = StreamingModel()
    with_model(monkeypatch, model)
    found = events(web.post("/chat", json={"message": NEW_ENGLAND}))
    assert kinds(found) == ["tool_start", "tool_result", "done"]
    picked = {"calls": [{"name": "airport_profile", "args": {"code": "BOS"}}]}
    assert kinds(events(web.post("/chat", json=picked)))[-1] == "done"
    assert model.seen == []


def test_the_cap_starts_again_on_a_new_utc_day(monkeypatch):
    monkeypatch.setenv("MAX_MODEL_QUESTIONS_PER_DAY", "1")
    today = [date(2026, 10, 12)]
    cap = server.DailyCap(clock=lambda: today[0])
    assert cap.take() and not cap.take()
    today[0] = date(2026, 10, 13)
    assert cap.take()


@pytest.mark.parametrize("text", ["lots", "-5", "1.5"])
def test_a_mistyped_cap_keeps_a_cap(monkeypatch, text):
    monkeypatch.setenv("MAX_MODEL_QUESTIONS_PER_DAY", text)
    assert server.DailyCap().limit() == server.INVALID_CAP_FALLBACK
