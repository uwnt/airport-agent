"""Talk mode: a spoken conversation with the agent, relayed by this server (decision D29).

The browser opens a WebSocket to /talk (registered in server.py, which checks the guards first).
The server opens a Live API session (llm.open_live: the typed chat's tools and system prompt) and
relays between the two, so the API key never leaves the server:
- browser to server: binary frames are microphone audio, 16-bit PCM at 16 kHz, mono; text frames
  are ignored (typed turns go through the typed chat, not here);
- server to browser: binary frames are the model's speech, 16-bit PCM at 24 kHz, mono (binary,
  not base64 in JSON: a third smaller and nothing to decode); text frames are JSON events
  {"event": kind, "data": {...}}, with the typed chat's shapes where they overlap:
  `tool_start` {name, args}, `tool_result` {name, args, result} (the page draws its tables from
  these), `heard` / `said` {text} (transcripts), `state` {state: listening, thinking or
  speaking}, `interrupted` {}, `error` {message} and `closed` {message}.

Tools run here, through the same `run_tool` as a typed question, at most MAX_TOOL_CALLS per
spoken turn. A session ends when the browser disconnects, after MAX_SECONDS, or after
IDLE_SECONDS with nothing said by either side; the Live API session is closed with it.
"""

import asyncio
import json
import logging
import os
import time
from urllib.parse import urlsplit

from airport_agent import llm

log = logging.getLogger(__name__)

MAX_SECONDS = 5 * 60  # one Talk session at most; each session counts as one question for the cap
IDLE_SECONDS = 60  # nothing heard, said or run (refused tool calls do not count) for this long
TICK_SECONDS = 1.0  # how often the time limits are checked
MAX_AUDIO_BYTES = 64_000  # one microphone frame (2 s at 16 kHz); the page sends about 0.1 s
AUDIO_BYTES_PER_SECOND = 32_000  # real time: 16 kHz, 2 bytes a sample, one channel
AUDIO_BURST = 2  # how far ahead of real time the microphone may run (network jitter)

OFF_MESSAGE = "Talk mode is switched off on this server."
LIMIT_MESSAGE = "This talk reached its {minutes}-minute limit. Press Talk to start a new one."
IDLE_MESSAGE = "This talk ended after {seconds} seconds of silence. Press Talk to start again."
FAILED_MESSAGE = "The voice connection failed. Press Talk to try again."
AUDIO_RATE_MESSAGE = "Audio arrived faster than anyone speaks, so this talk was ended."
TOOL_LIMIT_RESULT = {"error": "tool-call limit reached for this question"}
TOOL_ABUSE_MESSAGE = "The assistant kept asking for lookups past the limit, so this talk was ended."
clock = time.monotonic  # replaced in tests, so the time limits are tried without waiting


def enabled(env=None):
    """True when TALK_MODE=on (off by default: voice costs more and is newer than typed chat)."""
    env = os.environ if env is None else env
    return env.get("TALK_MODE", "").strip().lower() == "on"


def same_origin(headers):
    """True if the page that opened the socket came from this host (browsers always send Origin).

    Without the check any web site could open a Talk session from its visitors' browsers.
    """
    origin, host = headers.get("origin"), headers.get("host")
    return bool(origin and host) and urlsplit(origin).netloc.lower() == host.lower()


async def send_event(ws, kind, data=None):
    await ws.send_text(json.dumps({"event": kind, "data": data or {}}, ensure_ascii=False))


async def refuse(ws, message):
    """Tell the page why in plain words, then close (code 1008: policy violation)."""
    await ws.accept()
    await send_event(ws, "error", {"message": message})
    await ws.close(code=1008)


async def relay(ws, run_tool, open_live=None, max_tool_calls=None):
    """Relay one accepted WebSocket and one Live API session until either ends or time runs out."""
    open_live = open_live or llm.open_live
    max_tool_calls = max_tool_calls or llm.settings_from_env().max_tool_calls
    started = last_activity = clock()

    def active():
        nonlocal last_activity
        last_activity = clock()

    def audio_allowed(received):
        # A script could push audio far faster than real time into one billed session. Counted
        # from the start, with one second's grace so the first frames always pass.
        elapsed = clock() - started
        return received <= AUDIO_BYTES_PER_SECOND * AUDIO_BURST * (elapsed + 1)

    async def from_browser(live):
        audio_received = 0
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return None
            if message.get("bytes"):
                audio_received += len(message["bytes"])
                if not audio_allowed(audio_received):
                    await send_event(ws, "error", {"message": AUDIO_RATE_MESSAGE})
                    return AUDIO_RATE_MESSAGE
                await live.send_audio(message["bytes"][:MAX_AUDIO_BYTES])

    async def from_model(live):
        calls_this_turn, refused, speaking, answer_due, answered = 0, 0, False, False, False
        async for event in live.events():
            kind = event["kind"]
            if kind in ("heard", "said", "audio"):
                active()
            if kind == "turn_complete" and answer_due:
                # The Live API ends the model's turn at a tool call and answers in a new turn
                # once it has the results: the spoken exchange (and the page's card) goes on.
                answer_due = False
                continue
            if kind in ("tool_calls", "audio", "said", "interrupted"):
                answer_due = kind == "tool_calls"
            if kind in ("audio", "said"):
                answered = True
            if kind == "audio":
                if not speaking:
                    speaking = True
                    await send_event(ws, "state", {"state": "speaking"})
                await ws.send_bytes(event["data"])
            elif kind in ("heard", "said"):
                await send_event(ws, kind, {"text": event["text"]})
            elif kind == "tool_calls":
                await send_event(ws, "state", {"state": "thinking"})
                results, ran = [], False
                for call in event["calls"]:
                    name, args = call["name"], call["args"]
                    if calls_this_turn >= max_tool_calls:
                        refused += 1
                        results.append((call["id"], name, TOOL_LIMIT_RESULT))
                        continue
                    calls_this_turn += 1
                    ran = True
                    active()
                    await send_event(ws, "tool_start", {"name": name, "args": args})
                    result = await asyncio.to_thread(run_tool, name, args)
                    await send_event(
                        ws, "tool_result", {"name": name, "args": args, "result": result}
                    )
                    results.append((call["id"], name, result))
                await live.send_tool_results(results)
                # A refused call has nothing to wait for: its turn end must reach the page.
                answer_due = ran
                if refused >= 2:
                    await send_event(ws, "error", {"message": TOOL_ABUSE_MESSAGE})
                    return TOOL_ABUSE_MESSAGE
            elif kind in ("interrupted", "turn_complete"):
                if kind == "interrupted":
                    await send_event(ws, "interrupted")
                elif answered:
                    # Counts restart with a real answer, not with a turn that only hit the limit.
                    calls_this_turn, refused, answered = 0, 0, False
                speaking = False
                await send_event(ws, "state", {"state": "listening"})
        return FAILED_MESSAGE  # the model's side ended on its own

    async def watch_time():
        while True:
            await asyncio.sleep(TICK_SECONDS)
            now = clock()
            if now - started >= MAX_SECONDS:
                return LIMIT_MESSAGE.format(minutes=MAX_SECONDS // 60)
            if now - last_activity >= IDLE_SECONDS:
                return IDLE_MESSAGE.format(seconds=IDLE_SECONDS)

    try:
        async with open_live() as live:
            await send_event(ws, "state", {"state": "listening"})
            tasks = [asyncio.create_task(job(live)) for job in (from_browser, from_model)]
            tasks.append(asyncio.create_task(watch_time()))
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            ending = next(iter(done)).result()
    except Exception:
        # The SDK's errors never hold the key, but the page only needs to know it failed.
        log.exception("talk session failed")
        ending = FAILED_MESSAGE
    if ending is None:
        return  # the browser left: nobody to tell
    try:
        await send_event(ws, "closed", {"message": ending})
        await ws.close()
    except Exception:  # the browser may have gone at the same moment
        log.debug("talk socket already closed")
