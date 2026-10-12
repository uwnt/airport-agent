"""Talk mode (/talk) with a fake Live API session: no network, no key, no microphone."""

import asyncio
import json
import shutil
import time
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from google.genai import types
from starlette.websockets import WebSocketDisconnect

from airport_agent import llm, server, talk, tools
from airport_agent.data.store import FileStore

SAME_ORIGIN = {"origin": "http://testserver"}
NEW_ENGLAND = {"region": "New England"}


@pytest.fixture
def web(tmp_path_factory, sample_cache, monkeypatch):
    """The app with one data snapshot, Talk mode on, a key set and a fresh daily cap."""
    root = tmp_path_factory.mktemp("store")
    shutil.copytree(sample_cache, root / "latest-2026-10-11")
    manifest = {"version": "latest-2026-10-11", "as_of": "2026-10-11", "sources": {}}
    (root / "latest-2026-10-11" / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("DATA_STORE", f"file://{root}")
    monkeypatch.setattr(server, "data", server.DataVersion(FileStore(root), clock=lambda: 0.0))
    monkeypatch.setattr(server, "daily_cap", server.DailyCap())
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("TALK_MODE", "on")
    monkeypatch.delenv("MAX_MODEL_QUESTIONS_PER_DAY", raising=False)
    return TestClient(server.app)


class FakeLive:
    """Plays back scripted model events; after a tool call it waits for the tool results."""

    def __init__(self, script):
        self.script = list(script)
        self.audio, self.texts, self.tool_results = [], [], []
        self.answered = asyncio.Event()
        self.closed = False

    async def send_audio(self, pcm):
        self.audio.append(pcm)

    async def send_text(self, text):
        self.texts.append(text)

    async def send_tool_results(self, results):
        self.tool_results.extend(results)
        self.answered.set()

    async def events(self):
        for event in self.script:
            yield event
            if event["kind"] == "tool_calls":
                await self.answered.wait()
                self.answered.clear()
        await asyncio.Event().wait()  # the session stays open until the relay ends it


@pytest.fixture
def live(monkeypatch):
    """Replace the Live API with a FakeLive; set `.script` before connecting."""
    fake = FakeLive([])

    @asynccontextmanager
    async def open_live():
        try:
            yield fake
        finally:
            fake.closed = True

    monkeypatch.setattr(llm, "open_live", open_live)
    return fake


def connect(web, headers=SAME_ORIGIN):
    return web.websocket_connect("/talk", headers=headers)


def tool_call(name, args, call_id="c1"):
    return {"id": call_id, "name": name, "args": args}


def leave(ws, live):
    """Leave as a browser does, and wait until the server has closed the model session.

    TestClient cancels the app if it is still running when the `with` block ends.
    """
    ws.send({"type": "websocket.disconnect", "code": 1000})
    wait_until(lambda: live.closed)


def wait_until(condition, seconds=2.0):
    end = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.01)


def test_talk_is_refused_when_switched_off(web, monkeypatch, live):
    monkeypatch.delenv("TALK_MODE")
    with connect(web) as ws:
        assert ws.receive_json() == {"event": "error", "data": {"message": talk.OFF_MESSAGE}}
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    assert web.get("/info").json()["talk"] is False


def test_info_offers_talk_only_when_on_and_a_key_is_set(web, monkeypatch):
    assert web.get("/info").json()["talk"] is True
    monkeypatch.delenv("GEMINI_API_KEY")
    assert web.get("/info").json()["talk"] is False


def test_talk_from_another_site_is_refused(web, live):
    for headers in ({"origin": "https://elsewhere.example"}, {}):
        with pytest.raises(WebSocketDisconnect) as refused:
            with connect(web, headers):
                pass
        assert refused.value.code == 1008


def test_talk_is_refused_over_the_daily_cap(web, monkeypatch, live):
    monkeypatch.setenv("MAX_MODEL_QUESTIONS_PER_DAY", "1")
    with connect(web) as ws:
        assert ws.receive_json()["data"] == {"state": "listening"}
        leave(ws, live)
    with connect(web) as ws:  # the second session of the day
        assert ws.receive_json() == {"event": "error", "data": {"message": server.CAP_MESSAGE}}
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_a_spoken_tool_call_runs_the_real_tool_and_draws_like_typed_chat(web, live):
    live.script = [
        {"kind": "heard", "text": "Rank New England"},
        {"kind": "tool_calls", "calls": [tool_call("rank_airports", NEW_ENGLAND)]},
        {"kind": "audio", "data": b"\x01\x02\x03\x04"},
        {"kind": "said", "text": "BDL ranks first."},
        {"kind": "turn_complete"},
    ]
    with connect(web) as ws:
        ws.send_bytes(b"\x00\x00" * 160)  # 10 ms of silence from the microphone
        got = [ws.receive_json() for _ in range(6)]
        audio = ws.receive_bytes()
        rest = [ws.receive_json() for _ in range(2)]
        leave(ws, live)
    kinds = ["state", "heard", "state", "tool_start", "tool_result", "state"]
    assert [e["event"] for e in got] == kinds
    assert [got[i]["data"]["state"] for i in (0, 2, 5)] == ["listening", "thinking", "speaking"]
    assert got[3]["data"] == {"name": "rank_airports", "args": NEW_ENGLAND}
    assert audio == b"\x01\x02\x03\x04"
    assert rest == [
        {"event": "said", "data": {"text": "BDL ranks first."}},
        {"event": "state", "data": {"state": "listening"}},
    ]
    assert live.audio == [b"\x00\x00" * 160]

    # The same tool_result event as a typed request for the same tool (the page's table source).
    typed = web.post("/chat", json={"calls": [{"name": "rank_airports", "args": NEW_ENGLAND}]})
    blocks = [b.split("\n") for b in typed.text.strip().split("\n\n")]
    typed_result = next(json.loads(b[1][6:]) for b in blocks if b[0] == "event: tool_result")
    assert got[4]["data"] == typed_result
    assert typed_result["result"]["rows"]
    assert live.tool_results == [("c1", "rank_airports", typed_result["result"])]


def test_speaking_state_comes_before_the_audio(web, live):
    live.script = [{"kind": "audio", "data": b"\x05\x06"}, {"kind": "turn_complete"}]
    with connect(web) as ws:
        assert ws.receive_json()["data"] == {"state": "listening"}
        assert ws.receive_json()["data"] == {"state": "speaking"}
        assert ws.receive_bytes() == b"\x05\x06"
        assert ws.receive_json()["data"] == {"state": "listening"}
        leave(ws, live)


def test_tool_calls_past_the_limit_are_answered_with_an_error(web, monkeypatch, live):
    monkeypatch.setenv("MAX_TOOL_CALLS", "1")
    calls = [
        tool_call("rank_airports", NEW_ENGLAND, "a"),
        tool_call("airport_profile", {"code": "BDL"}, "b"),
    ]
    live.script = [{"kind": "tool_calls", "calls": calls}]
    with connect(web) as ws:
        kinds = [ws.receive_json()["event"] for _ in range(4)]
        wait_until(lambda: len(live.tool_results) == 2)
        leave(ws, live)
    assert kinds == ["state", "state", "tool_start", "tool_result"]
    assert live.tool_results[1] == ("b", "airport_profile", talk.TOOL_LIMIT_RESULT)


def test_a_typed_turn_goes_to_the_model_as_text(web, live):
    with connect(web) as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"text": "  Rank New England  "}))
        wait_until(lambda: live.texts)
        leave(ws, live)
    assert live.texts == ["Rank New England"]


@pytest.mark.parametrize(
    "now, message",
    [
        (talk.MAX_SECONDS, talk.LIMIT_MESSAGE.format(minutes=talk.MAX_SECONDS // 60)),
        (talk.IDLE_SECONDS, talk.IDLE_MESSAGE.format(seconds=talk.IDLE_SECONDS)),
    ],
)
def test_session_ends_at_its_time_limits(web, monkeypatch, live, now, message):
    clock = [0.0]
    monkeypatch.setattr(talk, "clock", lambda: clock[0])
    monkeypatch.setattr(talk, "TICK_SECONDS", 0.01)
    with connect(web) as ws:
        assert ws.receive_json()["data"] == {"state": "listening"}
        clock[0] = now
        assert ws.receive_json() == {"event": "closed", "data": {"message": message}}
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    assert live.closed


def test_browser_leaving_closes_the_model_session(web, live):
    with connect(web) as ws:
        ws.receive_json()
        leave(ws, live)
    assert live.closed


def test_live_messages_become_plain_events():
    message = types.LiveServerMessage(
        server_content=types.LiveServerContent(
            input_transcription=types.Transcription(text="rank it"),
            model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=b"\x01"))]),
            output_transcription=types.Transcription(text="BDL"),
            turn_complete=True,
        ),
        tool_call=types.LiveServerToolCall(
            function_calls=[types.FunctionCall(id="x", name="rank_airports", args=NEW_ENGLAND)]
        ),
    )
    assert llm.live_events(message) == [
        {"kind": "heard", "text": "rank it"},
        {"kind": "audio", "data": b"\x01"},
        {"kind": "said", "text": "BDL"},
        {"kind": "turn_complete"},
        {"kind": "tool_calls", "calls": [tool_call("rank_airports", NEW_ENGLAND, "x")]},
    ]
    assert llm.live_events(
        types.LiveServerMessage(server_content=types.LiveServerContent(interrupted=True))
    ) == [{"kind": "interrupted"}]


def test_live_tools_are_the_typed_chat_tools(monkeypatch):
    declarations = llm.live_function_declarations(tools.TOOL_DECLARATIONS)
    assert [d["name"] for d in declarations] == [t["name"] for t in tools.TOOL_DECLARATIONS]
    assert declarations[0]["parameters_json_schema"] == tools.TOOL_DECLARATIONS[0]["parameters"]
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "other-live-model")
    assert llm.live_model() == "other-live-model"
    monkeypatch.delenv("GEMINI_LIVE_MODEL")
    assert llm.live_model() == llm.DEFAULT_LIVE_MODEL


def test_the_microphone_worklet_is_served_from_this_site(web):
    # The page's content policy allows scripts from this site only, so the worklet is a file.
    assert web.get("/static/talk-worklet.js").status_code == 200
    assert web.get("/").text.count('id="talk"') == 1


def test_audio_faster_than_real_time_ends_the_session(web, monkeypatch, live):
    clock = [0.0]
    monkeypatch.setattr(talk, "clock", lambda: clock[0])
    allowance = talk.AUDIO_BYTES_PER_SECOND * talk.AUDIO_BURST  # the first second's share
    with connect(web) as ws:
        assert ws.receive_json()["data"] == {"state": "listening"}
        ws.send_bytes(b"\x00" * allowance)
        clock[0] = 10.0  # ten seconds of real-time speech later, ten seconds' audio still passes
        for _ in range(10):
            ws.send_bytes(b"\x00" * talk.AUDIO_BYTES_PER_SECOND)
        wait_until(lambda: len(live.audio) == 11)
        ws.send_bytes(b"\x00" * allowance * 10)  # then a burst far ahead of real time
        wait_until(lambda: live.closed)  # with a deadline, so a missing limit fails, not hangs
        assert ws.receive_json() == {
            "event": "error",
            "data": {"message": talk.AUDIO_RATE_MESSAGE},
        }
        assert ws.receive_json()["event"] == "closed"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    assert live.closed
    assert len(live.audio) == 11  # the burst never reached the model


def test_the_snapshot_is_looked_up_off_the_event_loop(web, monkeypatch, live):
    lookup, seen = server.snapshot_for, []

    def snapshot_for(version):
        try:
            asyncio.get_running_loop()
            seen.append("on the event loop")
        except RuntimeError:
            seen.append("in a worker thread")
        return lookup(version)

    monkeypatch.setattr(server, "snapshot_for", snapshot_for)
    with connect(web) as ws:
        assert ws.receive_json()["data"] == {"state": "listening"}
        leave(ws, live)
    assert seen == ["in a worker thread"]
