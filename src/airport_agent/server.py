"""Web server: the chat page at /, its data at /info, answers at POST /chat, and /health.

Talk mode (spoken questions, off unless TALK_MODE=on) is the WebSocket /talk: see talk.py.

Run: doppler run -- uv run uvicorn airport_agent.server:app --host 127.0.0.1 --port 8100

The page (static/: plain HTML, CSS and JavaScript, no build step) sends each question to
POST /chat with the conversation so far (the server keeps no conversation state) and the data
version picked. The answer comes back as server-sent events, in this order:
- `tool_start` {name, args}: a tool is about to run;
- `tool_result` {name, args, result}: its JSON result; the page draws tables, score bars and the
  "How I got this" panel from these, never from the model's text;
- `text` {text}: a piece of the answer as the model writes it (Markdown);
- `done` {text}: the whole answer; or `error` {message}: what went wrong, in plain words.
Without GEMINI_API_KEY there is no model: the suggested questions and the picker run their tools
directly, and the answer is a fixed-wording summary of the results.

Daily cap (for the public site): MAX_MODEL_QUESTIONS_PER_DAY limits the questions sent to the
model per UTC day; unset means no cap (local runs, Docker). Over the cap a free-form question gets
an `error` event with CAP_MESSAGE, and a suggested question or the picker runs its tools directly,
as without a model. The count is kept in memory (see DailyCap).

Data: the server answers from one snapshot of the data store (DATA_STORE, see data/store.py),
read fully into memory: the latest at startup. On use, once DATA_CHECK_MINUTES (default 5) have
passed, it asks the store for its latest again and, if that is a new one, loads it and switches to
it in one step, so a new snapshot from `airport-agent refresh` is picked up without a restart.
/health reports the version of that same loaded snapshot.
At startup the server also looks for a newer GitHub data release (DATA_RELEASES, on unless "off")
in the background, and the Data panel can get or build newer data: see data_panel.py.
"""

import asyncio
import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from airport_agent import cli, data_panel, llm, talk, tools
from airport_agent.data import faa_capacity
from airport_agent.data.cache import CacheMissingError, load_config
from airport_agent.data.metrics import load_cache
from airport_agent.data.store import open_store, read_manifest, snapshot_problem
from airport_agent.scoring import load_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """One data snapshot, fully loaded: its version, its as-of date and every summary (`cache`).

    Answers pass `cache` to the metrics functions (`airport_metrics(code, cache=...)`), so they
    never read the store themselves.
    """

    version: str
    as_of: str
    cache: dict


class DataVersion:
    """The snapshot the server answers from, re-checked every DATA_CHECK_MINUTES.

    `store` and `clock` can be replaced in tests (a fake store, a fake clock: no sleeping).
    """

    def __init__(self, store=None, clock=time.monotonic):
        self.store, self.clock = store, clock
        self.snapshot, self.checked_at = None, None
        self.minutes = 5.0
        text = os.environ.get("DATA_CHECK_MINUTES", "5")
        try:
            minutes = float(text)
            if not minutes >= 0:
                raise ValueError("must not be negative")
            self.minutes = minutes
        except ValueError:
            log.warning("DATA_CHECK_MINUTES=%r is not a number of minutes, using 5", text)

    def current(self):
        """The Snapshot in use (None while the store has none); checks the store first if due.

        A newer snapshot is loaded completely before it replaces the one in use, in a single
        assignment: a caller gets the old snapshot or the new one, never a mix. If it can't be
        loaded, the old one stays in use and the next check tries again.
        """
        now = self.clock()
        if self.checked_at is None or now - self.checked_at >= self.minutes * 60:
            self.checked_at = now
            store = self.store or open_store()
            try:
                latest = store.latest()
            except OSError as error:
                log.warning("Can't reach the data store, keeping the snapshot in use: %s", error)
                return self.snapshot
            if latest and (self.snapshot is None or latest != self.snapshot.version):
                try:
                    folder = store.get(latest)
                    loaded = Snapshot(latest, read_manifest(folder)["as_of"], load_cache(folder))
                except (OSError, ValueError, KeyError) as error:
                    log.warning(
                        "Can't load data snapshot %r, keeping the one in use: %s", latest, error
                    )
                else:
                    self.snapshot = loaded
        return self.snapshot


data = DataVersion()


@asynccontextmanager
async def lifespan(app):
    data.current()  # load the latest snapshot at startup
    data_panel.start_release_check()  # in the background: startup never waits on GitHub
    yield


app = FastAPI(title="Airport Investment Intelligence Agent", lifespan=lifespan)
STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(data_panel.router)  # the Data panel: /data/status, /data/latest, /data/refresh


def current_commit():
    """The deployed commit (RELEASE_SHA, set at image build), else the local git HEAD."""
    release_sha = os.environ.get("RELEASE_SHA", "").strip()
    if release_sha:
        return release_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            cwd=Path(__file__).resolve().parent,  # this package's repo, not the caller's directory
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@app.get("/health")
def health():
    """Says what this running copy is: its code version, data version and model."""
    snapshot = data.current()
    return {
        "status": "ok",
        "commit": current_commit(),
        "data_version": snapshot.version if snapshot else None,
        "snapshot_date": snapshot.as_of if snapshot else None,
        "model": os.environ.get("GEMINI_MODEL"),
    }


# --- The chat page ---------------------------------------------------------------------------

REGION_CHOICES = ["New England", "LA area"]  # how the picker shows data/regions.py's names
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


# The page loads only its own files: no third-party script, style or request, no inline script.
PAGE_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


@app.get("/", include_in_schema=False)
def page():
    return FileResponse(STATIC / "index.html", headers={"Content-Security-Policy": PAGE_POLICY})


def _store():
    return data.store or open_store()


def point_in_time_versions():
    """The point-in-time snapshots in the store (2021-12, 2019-12, ...), newest first."""
    root = _store().root
    folders = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    names = [
        p.name for p in folders if not p.name.startswith("latest") and snapshot_problem(p) is None
    ]
    return sorted(names, reverse=True)


def snapshot_for(version):
    """(version, folder) of the snapshot the tools read; "latest" is the one the server loaded.

    Raises LookupError, in plain words, for a version the store doesn't have.
    """
    if version == "latest":
        snapshot = data.current()
        if snapshot is None:
            raise LookupError("No data snapshot is loaded yet; build one: airport-agent refresh")
        version = snapshot.version
    elif version not in point_in_time_versions():
        raise LookupError(f"No data version {version!r}; pick latest or one of the listed dates.")
    try:
        return version, _store().get(version)
    except (CacheMissingError, ValueError) as error:
        raise LookupError(str(error)) from error


def period_end(as_of):
    """(year, month) in which a source's as-of text ends, or None if it can't be read.

    Reads the forms the manifests use: "2026-10-11", "Aug 2025 to Jul 2026", "2026 Q1", "2023";
    for a range, the end ("... to <end>").
    """
    text = str(as_of).split(" to ")[-1]
    if m := re.search(r"(\d{4})-(\d{2})-\d{2}", text):
        return int(m[1]), int(m[2])
    if m := re.search(r"(\d{4}) Q([1-4])", text):
        return int(m[1]), int(m[2]) * 3
    if m := re.search(r"([A-Z][a-z]{2}) (\d{4})", text):
        if m[1] in MONTHS:
            return int(m[2]), MONTHS.index(m[1]) + 1
    if m := re.search(r"\b(\d{4})\b", text):
        return int(m[1]), 12
    return None


def is_stale(as_of, reference, months):
    """True if the source's data ends more than `months` whole months before `reference`."""
    end = period_end(as_of)
    if end is None:
        return False
    return (reference.year - end[0]) * 12 + (reference.month - end[1]) > months


# --- Daily cap on model questions (the public site) -------------------------------------------


class DailyCap:
    """Counts the questions sent to the model per UTC day and refuses those over the cap.

    The count lives in memory only, so it starts again at 0 whenever the server restarts (and Fly
    stops an idle machine and starts it on the next visit). It is a guard against one runaway
    client, not an exact limit; the Gemini key's own spending cap is the last guard.
    """

    def __init__(self, clock=lambda: datetime.now(UTC).date()):
        self.clock = clock
        self.lock = threading.Lock()
        self.day, self.count = None, 0

    def limit(self):
        """Today's cap from MAX_MODEL_QUESTIONS_PER_DAY, or None for no cap (the variable unset)."""
        text = os.environ.get("MAX_MODEL_QUESTIONS_PER_DAY", "").strip()
        if not text:
            return None
        try:
            limit = int(text)
        except ValueError:
            limit = -1
        if limit < 0:
            # A typo must not switch the guard off on a public site.
            log.warning("MAX_MODEL_QUESTIONS_PER_DAY=%r is not a whole number >= 0", text)
            return INVALID_CAP_FALLBACK
        return limit

    def take(self):
        """Count one model question; False (and not counted) if today's cap is already reached."""
        limit = self.limit()
        with self.lock:
            today = self.clock()
            if today != self.day:
                self.day, self.count = today, 0
            if limit is not None and self.count >= limit:
                return False
            self.count += 1
            return True


INVALID_CAP_FALLBACK = 300
daily_cap = DailyCap()


@app.get("/info")
def info(version: str = "latest"):
    """What the page needs to draw itself: mode, versions, sources with as-of dates, choices."""
    try:
        name, folder = snapshot_for(version)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return info_payload(name, folder, date.today() if version == "latest" else None)


def info_payload(name, folder, today=None):
    """The /info body for snapshot `name` in `folder`; the release check builds it too.

    Staleness is judged against `today`, or, for a point-in-time snapshot (None), its as-of date.
    """
    manifest = read_manifest(folder)
    months = load_config()["freshness"]["stale_after_months"]
    reference = today or date.fromisoformat(manifest["as_of"])
    sources = [
        {
            "name": key,
            "source": s.get("source", key),
            "as_of": s.get("as_of"),
            "stale": is_stale(s.get("as_of"), reference, months),
        }
        for key, s in sorted(manifest.get("sources", {}).items())
    ]
    # The committed FAA table is not in any snapshot's manifest, so it is listed here.
    sources.append(
        {
            "name": "faa_capacity",
            "source": faa_capacity.SOURCE,
            "as_of": "2014",
            "stale": is_stale("2014", reference, months),
        }
    )
    return {
        "model": llm.has_api_key(),
        "talk": talk.enabled() and llm.has_api_key(),
        "versions": ["latest", *point_in_time_versions()],
        "version": name,
        "as_of": manifest["as_of"],
        "sources": sources,
        "stale_after_months": months,
        "stale_reference": reference.isoformat(),
        "questions": [question for question, _ in cli.FIXED_QUESTIONS],
        "presets": list(load_settings().scoring["presets"]),
        "regions": REGION_CHOICES,
    }


MAX_ARGS_CHARS = 1_000  # one picker call's arguments, as JSON
# Request size (the site is public, and every character is sent to the model): one question, and
# the earlier turns the page sends back as text so follow-ups work. The page (static/app.js) trims
# its history to fit these, dropping the oldest question-and-answer pairs first.
MAX_QUESTION_CHARS = 2_000
MAX_HISTORY_TURNS = 10  # five questions and their answers
MAX_HISTORY_CHARS = 20_000  # all earlier turns together


class Turn(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(max_length=MAX_HISTORY_CHARS)


class Call(BaseModel):
    name: str = Field(max_length=40)
    args: dict = Field(default_factory=dict)

    @field_validator("args")
    @classmethod
    def _small(cls, args):
        # The picker sends a region, a few codes and a preset; the reply repeats the arguments,
        # so an unbounded value would come back several times larger.
        if len(json.dumps(args)) > MAX_ARGS_CHARS:
            raise ValueError(f"tool arguments must be under {MAX_ARGS_CHARS} characters as JSON")
        return args


class ChatRequest(BaseModel):
    message: str = Field("", max_length=MAX_QUESTION_CHARS)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    version: str = Field("latest", max_length=40)
    calls: list[Call] = Field(default_factory=list, max_length=4)  # the picker: tools to run

    @field_validator("history")
    @classmethod
    def _history_small(cls, history):
        # Each turn is under the limit on its own; together they must be too, or ten long turns
        # would make one question ten times the size.
        total = sum(len(turn.text) for turn in history)
        if total > MAX_HISTORY_CHARS:
            raise ValueError(
                f"the earlier conversation is {total} characters; at most {MAX_HISTORY_CHARS} "
                "are accepted (start a new conversation, or reload the page)"
            )
        return history


CAP_MESSAGE = (
    "This site has reached today's limit of questions to the model; it resets at midnight UTC. "
    "The suggested questions and the rank / compare / profile picker still work."
)
NO_KEY_MESSAGE = (
    "Free-form questions need the model, and no GEMINI_API_KEY is set on the server. "
    "Pick a suggested question, or use the rank / compare / profile picker."
)


def make_session(run_tool):
    """A model chat whose tools read the picked snapshot; tests replace this with a fake model."""
    return llm.ChatSession(run_tool=run_tool)


def summary(name, result):
    """A fixed-wording summary of one tool result (no model), every number copied from it."""
    if name in ("rank_airports", "compare_airports") and result.get("rows"):
        top = result["rows"][0]
        text = (
            f"**{top['code']} {top['name']}** ranks first here, with a score of {top['score']:g} "
            f"under the {result['preset']} preset (national rank {top['national_rank']} of "
            f"{result['ranked_count']} ranked airports). The bars show each airport's points."
        )
        not_ranked = [f"{n['code']} ({n['reason']})" for n in result.get("not_ranked", [])]
        return text + (" Not ranked: " + "; ".join(not_ranked) + "." if not_ranked else "")
    lead = f"{result['summary']}\n\n" if name == "demand_pressure" and "summary" in result else ""
    return lead + "```text\n" + cli.format_result(name, result) + "\n```"


def _event(kind, payload):
    return f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream(work):
    """Run `work(emit)` in a thread and yield each emitted event as soon as it is emitted."""
    events = queue.Queue()

    def run():
        try:
            work(lambda kind, payload: events.put((kind, payload)))
        except Exception as error:  # a model or network failure ends this answer, not the server
            log.exception("chat answer failed")
            message = f"The answer failed ({type(error).__name__}: {error})"[:500]
            events.put(("error", {"message": message + ". Try again."}))
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()
    while (item := events.get()) is not None:
        yield _event(*item)


def _run_calls(calls, run_tool, emit):
    """Run tools directly (no model) and end with a fixed-wording summary of their results."""
    parts = []
    for name, args in calls:
        emit("tool_start", {"name": name, "args": args})
        result = run_tool(name, args)
        emit("tool_result", {"name": name, "args": args, "result": result})
        if "error" in result:
            emit("error", {"message": result["error"]})
            return
        parts.append(summary(name, result))
    emit("done", {"text": "\n\n".join(parts)})


def tool_runner(folder):
    """run_tool(name, args) for answers from the snapshot in `folder`."""

    def run_tool(name, args):
        # compare_over_time reads two versions of its own choosing from the store.
        return tools.run_tool(name, args, None if name == "compare_over_time" else folder)

    return run_tool


@app.post("/chat")
def chat(request: ChatRequest):
    """Answer one question as server-sent events (see the module notes for the events)."""
    try:
        _, folder = snapshot_for(request.version)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    run_tool = tool_runner(folder)

    fixed = dict(cli.FIXED_QUESTIONS)
    if request.calls:
        calls = [(c.name, c.args) for c in request.calls]
    elif not request.message.strip():
        raise HTTPException(status_code=422, detail="Ask a question or pick one.")
    elif not llm.has_api_key():
        calls = fixed.get(request.message.strip())
        if calls is None:
            return StreamingResponse(
                iter([_event("error", {"message": NO_KEY_MESSAGE})]),
                media_type="text/event-stream",
            )
    elif not daily_cap.take():
        calls = fixed.get(request.message.strip())  # a suggested question still runs its tools
        if calls is None:
            return StreamingResponse(
                iter([_event("error", {"message": CAP_MESSAGE})]),
                media_type="text/event-stream",
            )
    else:
        calls = None

    def work(emit):
        if calls is not None:
            return _run_calls(calls, run_tool, emit)
        session = make_session(run_tool)
        session.history = llm.history_from_turns([t.model_dump() for t in request.history])
        answer = session.send(request.message.strip(), on_event=emit)
        emit("done", {"text": answer.text, "stopped_at_limit": answer.stopped_at_limit})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_stream(work), media_type="text/event-stream", headers=headers)


@app.websocket("/talk")
async def talk_socket(ws: WebSocket, version: str = "latest"):
    """A spoken conversation (Talk mode, off unless TALK_MODE=on): see talk.py for the frames."""
    if not talk.same_origin(ws.headers):
        await ws.close(code=1008)  # before accepting: the browser sees a refused connection
        return
    if not talk.enabled():
        return await talk.refuse(ws, talk.OFF_MESSAGE)
    if not llm.has_api_key():
        return await talk.refuse(ws, NO_KEY_MESSAGE)
    try:
        # A due snapshot reload or an older version's scan reads files: off the event loop, so
        # it never stalls the sessions already relaying.
        _, folder = await asyncio.to_thread(snapshot_for, version)
    except LookupError as error:
        return await talk.refuse(ws, str(error))
    if not daily_cap.take():  # one Talk session counts as one question
        return await talk.refuse(ws, CAP_MESSAGE)
    await ws.accept()
    await talk.relay(ws, tool_runner(folder))
