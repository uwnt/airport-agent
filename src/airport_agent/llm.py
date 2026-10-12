"""Every model call lives here (decision D3): Google Gemini with tools, in a loop we can read (D2).

The model reads the question, picks tools and explains their results; the tools compute every
number. This is the only module that imports the Google SDK, so another vendor touches only it.

How a question is answered (`ChatSession.send`):
1. The question is added to the conversation history, and the whole history goes to the model
   with the tool descriptions and the system prompt.
2. If the model asks for tools, each one is run and its result is added to the history; then
   the model is asked again. This repeats until it answers in text, or until MAX_TOOL_CALLS
   tools have run for this question (then it stops with a plain message).
3. The answer and the history stay, so a follow-up ("and what about Hartford?") has context.

Streaming (the web chat): `send(text, on_event=...)` reports each step as it happens, as
`on_event(kind, data)`: "tool_start" (name, args) before a tool runs, "tool_result" (name, args,
result) after it, and "text" (a piece of the answer) as the model writes it. With a listener the
model call streams (`stream=True`) and its steps are put back together from the stream's events
(`assemble_steps`), so the history is the same as without streaming.

Token usage: each model call reports how many tokens it read and wrote (`usage` on the
interaction; when streamed, on the final `interaction.completed` event). The client keeps the
last call's counts in `last_usage`, and `send` adds up its calls into `Answer.usage`: a dict
such as {"total_input_tokens": ..., "total_output_tokens": ..., "total_thought_tokens": ...},
empty when the client reports none (a test's fake model, for example).

Settings come from the environment, each with a default:
- GEMINI_API_KEY: the key; without it there is no model (the CLI offers fixed questions instead).
- GEMINI_MODEL: default `gemini-3.8-flash` (Flash tier, stable). A Pro-tier alternative is
  `gemini-3.1-pro-preview` (more careful on multi-tool questions, slower, costs more, preview).
- MAX_ANSWER_TOKENS (default 4096), MAX_TOOL_CALLS per question (default 8),
  REQUEST_TIMEOUT_SECONDS per model call (default 120).
- GEMINI_THINKING_LEVEL: minimal, low, medium or high (default low). Measured 2026-10-11 on one
  question: a call at the model's default level took about 44 s, at low about 11 s.
- GEMINI_LIVE_MODEL: the Talk mode's Live API model, default `gemini-3.8-live` (see the end of
  this module).

SDK calls follow Google's docs, read 2026-10-11 (google-genai 2.29.0): the Interactions API,
`client.interactions.create(model=..., input=history, tools=..., system_instruction=...,
generation_config={"max_output_tokens": ..., "thinking_level": ...}, store=False)`; the
response's `steps` include `function_call` steps (id, name, arguments), answered with
`function_result` steps. Streaming (`stream=True`) yields events: `step.start` (the step's type;
for a function call also its id and name), `step.delta` (`text`, `thought_signature`, or
`arguments_delta`: a piece of the arguments' JSON, to be joined), `step.stop`,
`interaction.completed` (no steps in it, but the call's `usage`) and `error`.
Token counting (read 2026-10-12): `client.models.count_tokens(model=..., contents=text)` returns
`total_tokens`, the input tokens of that text, without a model call.
- https://ai.google.dev/gemini-api/docs/tokens
- https://ai.google.dev/gemini-api/docs/streaming
- https://ai.google.dev/gemini-api/docs/function-calling
- https://ai.google.dev/gemini-api/docs/models
- https://googleapis.github.io/python-genai/
"""

import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.8-flash"
PRO_MODEL = "gemini-3.1-pro-preview"
# Retried: short-lived server errors only. Not 429: a spent daily quota comes back as 429 with a
# Retry-After of hours, and the SDK would sleep that long; the user should see the error at once.
RETRY = types.HttpRetryOptions(attempts=3, http_status_codes=[408, 500, 502, 503, 504])
# The token counts kept from a call's `usage` (the SDK's names); the per-modality lists are not.
USAGE_FIELDS = (
    "total_input_tokens",
    "total_output_tokens",
    "total_thought_tokens",
    "total_cached_tokens",
    "total_tool_use_tokens",
    "total_tokens",
)

SYSTEM_PROMPT = """\
You help investment analysts judge which US airports are most promising for terminal expansion.
You give decision support, not investment advice.

Numbers
- Every number you state must appear in a tool result from this conversation: a score, rank,
  percentile, points, measured value, value_pct, change, change_pct_points, count, date or
  weight. Copy it as the tool gave it (you may round to fewer decimals, and quote value_pct as a
  percentage). Never compute a new number (no differences, ratios, sums or averages of your own)
  and never recall one from memory.
  If you need a number no tool gives, say it isn't available.
- national_rank is an airport's place; ranked_count is how many airports are ranked ("national
  rank 77 of 138"). Never state ranked_count as an airport's rank. demand_pressure gives
  percentiles, not a rank.
- Percentiles are whole numbers; write them with the right ending ("61st", "72nd", "33rd",
  "64th percentile").
- Never claim an average, median or other statistic the tools did not return. The tools give
  percentiles: say "below the median airport" only as "below the 50th percentile", and don't
  call anything "above (or below) the national average".
- Before answering about an airport or region, call the tools; don't answer from memory. For
  "why" questions, call airport_profile (for verified facts) and demand_pressure. For "how has
  X changed since 2019 or 2021" questions, call compare_over_time (versions 2019-12, 2021-12,
  latest); quote its change fields, and say so when a signal is not available for a date.

Facts and general knowledge
- Facts about an airport (caps, curfews, runways, history) may be stated as fact only if they are
  in airport_profile's verified_facts; cite the note number and a source link, and state the
  fact's checked date ("checked 2026-10-11"). If a fact or a friction penalty has stale: true,
  say it may be out of date and give its review_by date (the penalty still applies).
- Anything else you add from your own knowledge must be marked "(general knowledge)" and must
  contain no numbers. That includes any name the tools did not give: an airport's full name, an
  airline's name for a carrier code (the tools give "UA", not the airline), facts about a city.
- bad_weather_capacity_loss (in airport_profile, 30 airports only, from 2014) is the share of
  hourly runway capacity lost in bad weather. It is about runways, never terminal space, and it
  is shown, not scored: never say it affects a score or rank. If it is missing, say the airport
  is not one of the 30 in the FAA's profiles.
- A friction penalty is our scoring's judgement of how hard expansion would be. It is not a
  cause of anything: never say a penalty causes delays, low growth or any other measured value.

Places
- "LA" means LAX, the airport; "LA area" means the Los Angeles region (LAX, SNA, BUR, LGB, ONT).
  Named regions: New England, LA area. A city name means its main airport (Hartford = BDL).
- Only lower-48 airports in the DOT fare data are ranked. Anchorage is not ranked; for it, use
  long_haul_share and airport_profile.
- If a tool returns an error, say so plainly, quote its reason as the tool gave it (don't
  guess another reason), and suggest what you can do instead.

Out of scope
- Cargo economics, financing, airline strategy and construction cost are out of scope. Only when
  a question asks about one of them, say so in one sentence and offer what you can do (rank,
  compare, profile, demand signals, change over time, Anchorage long-haul share).
  Otherwise don't mention scope.

Every answer
- Lead with the answer in plain words, then the supporting numbers (a short table is fine).
- Mention Low confidence flags and friction penalties when they apply.
- End with a section headed "Assumptions and data" listing: the preset and its weights (from
  weights_pct) if a score was used, any threshold or definition used, and each data source the
  tools used with its as_of date, exactly as the tools gave them.
"""

TOOL_LIMIT_MESSAGE = (
    "I stopped after {limit} tool calls without a final answer. Please ask a narrower question "
    "(one region or a few airports)."
)


@dataclass(frozen=True)
class Settings:
    model: str
    max_answer_tokens: int
    max_tool_calls: int
    timeout_seconds: float
    thinking_level: str = "low"


def settings_from_env(env=None):
    env = os.environ if env is None else env
    return Settings(
        model=env.get("GEMINI_MODEL") or DEFAULT_MODEL,
        max_answer_tokens=int(env.get("MAX_ANSWER_TOKENS") or 4096),
        max_tool_calls=int(env.get("MAX_TOOL_CALLS") or 8),
        timeout_seconds=float(env.get("REQUEST_TIMEOUT_SECONDS") or 120),
        thinking_level=env.get("GEMINI_THINKING_LEVEL") or "low",
    )


def has_api_key(env=None):
    env = os.environ if env is None else env
    return bool(env.get("GEMINI_API_KEY"))


class GeminiClient:
    """One model call: the whole history in, the model's new steps out (as plain dicts)."""

    def __init__(self, settings):
        self.settings = settings
        # Reads GEMINI_API_KEY from the environment.
        self.client = genai.Client(http_options=types.HttpOptions(retry_options=RETRY))
        self.last_usage = {}

    def next_steps(self, history, tools, system_prompt, on_text=None):
        """The model's next steps; with `on_text`, streamed, calling it with each piece of text."""
        request = dict(
            model=self.settings.model,
            input=history,
            tools=tools,
            system_instruction=system_prompt,
            generation_config={
                "max_output_tokens": self.settings.max_answer_tokens,
                "thinking_level": self.settings.thinking_level,
            },
            store=False,
            timeout=self.settings.timeout_seconds,
        )
        self.last_usage = {}
        if on_text is None:
            interaction = self.client.interactions.create(**request)
            data = interaction.model_dump(mode="json", exclude_none=True)
            self.last_usage = usage_counts(data.get("usage"))
            return data.get("steps") or []
        stream = self.client.interactions.create(**request, stream=True)
        events = (event.model_dump(mode="json", exclude_none=True) for event in stream)
        return assemble_steps(events, on_text, usage=self.last_usage)

    def count_tokens(self, text):
        """How many input tokens `text` is for this model, by the API's counter (no model call)."""
        response = self.client.models.count_tokens(model=self.settings.model, contents=text)
        return response.total_tokens or 0


class ModelError(RuntimeError):
    """The model reported an error in the middle of a streamed answer."""


def usage_counts(usage):
    """The token counts (whole numbers) from a call's `usage` dict; {} if there is none."""
    usage = usage or {}
    return {k: usage[k] for k in USAGE_FIELDS if isinstance(usage.get(k), int)}


def add_usage(total, usage):
    """Add one call's token counts into `total` (a dict), field by field."""
    for key, count in usage_counts(usage).items():
        total[key] = total.get(key, 0) + count
    return total


def assemble_steps(events, on_text, usage=None):
    """Join a stream's events (dicts) back into whole steps, as a non-streamed call returns them.

    Each piece of answer text is also passed to `on_text` as it arrives. Function-call arguments
    arrive as pieces of one JSON text and are decoded once the stream has ended. If `usage` (a
    dict) is given, the token counts from the `interaction.completed` event are put into it.
    """
    steps, arguments = {}, {}
    for event in events:
        kind = event.get("event_type")
        if kind == "error":
            raise ModelError((event.get("error") or {}).get("message") or "the model failed")
        if kind == "interaction.completed" and usage is not None:
            usage.update(usage_counts((event.get("interaction") or {}).get("usage")))
        index = event.get("index")
        if kind == "step.start":
            steps[index] = dict(event.get("step") or {})
        elif kind == "step.delta":
            step, delta = steps.setdefault(index, {}), event.get("delta") or {}
            if delta.get("type") == "text":
                piece = delta.get("text", "")
                content = step.setdefault("content", [])
                if not content or content[-1].get("type") != "text":
                    content.append({"type": "text", "text": ""})
                content[-1]["text"] += piece
                if piece and step.get("type") == "model_output":
                    on_text(piece)
            elif delta.get("type") == "thought_signature":
                step["signature"] = step.get("signature", "") + (delta.get("signature") or "")
            elif delta.get("type") == "arguments_delta":
                arguments[index] = arguments.get(index, "") + (delta.get("arguments") or "")
    for index, text in arguments.items():
        if text.strip():
            steps[index]["arguments"] = json.loads(text)
    return [steps[i] for i in sorted(steps)]


def history_from_turns(turns):
    """A conversation's earlier turns, as plain text, in the model's history format.

    `turns` is a list of {"role": "user" or "model", "text": ...}: what the web page keeps and
    sends back with each question, since the server keeps no conversation state. Only the text
    is kept, not earlier tool results, so the model calls tools again for a follow-up's numbers.
    """
    kinds = {"user": "user_input", "model": "model_output"}
    return [
        {"type": kinds[t["role"]], "content": [{"type": "text", "text": t["text"]}]}
        for t in turns
        if t.get("role") in kinds and t.get("text")
    ]


@dataclass
class ToolCall:
    name: str
    args: dict
    result: dict


@dataclass
class Answer:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stopped_at_limit: bool = False
    usage: dict = field(default_factory=dict)  # token counts summed over the model calls


def _text_of(steps):
    """The text parts of the model's output steps, joined."""
    parts = []
    for step in steps:
        if step.get("type") == "model_output":
            parts.extend(c.get("text", "") for c in step.get("content") or [] if c.get("text"))
    return "\n".join(parts).strip()


def _result_step(call, result):
    return {
        "type": "function_result",
        "name": call["name"],
        "call_id": call.get("id"),
        "result": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
    }


class ChatSession:
    """A conversation with the model; keeps the history so follow-up questions work.

    `client` needs one method, `next_steps(history, tools, system_prompt)` -> list of step dicts;
    tests pass a fake. If it also has `last_usage` (the token counts of its latest call), they
    are added up into `Answer.usage`. `run_tool(name, args)` -> dict runs a tool and never raises.
    """

    def __init__(self, client=None, settings=None, tools=None, run_tool=None, system_prompt=None):
        from airport_agent import tools as toolbox

        self.settings = settings or settings_from_env()
        self.client = client or GeminiClient(self.settings)
        self.tools = tools if tools is not None else toolbox.TOOL_DECLARATIONS
        self.run_tool = run_tool or toolbox.run_tool
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.history = []

    def reset(self):
        self.history = []

    def send(self, user_text, on_event=None):
        """Answer one user message; returns an Answer with the text and the tools it ran.

        `on_event(kind, data)`, if given, hears each step as it happens (see the module notes).
        If the model call fails, the history goes back to before this message and the error is
        raised, so the next message starts from a clean conversation.
        """
        start = len(self.history)
        try:
            return self._answer(user_text, on_event)
        except Exception:
            del self.history[start:]
            raise

    def _next_steps(self, on_event, usage):
        if on_event is None:
            steps = self.client.next_steps(self.history, self.tools, self.system_prompt)
        else:
            steps = self.client.next_steps(
                self.history,
                self.tools,
                self.system_prompt,
                on_text=lambda piece: on_event("text", {"text": piece}),
            )
        add_usage(usage, getattr(self.client, "last_usage", None))
        return steps

    def _answer(self, user_text, on_event=None):
        tell = on_event or (lambda kind, data: None)
        self.history.append(
            {"type": "user_input", "content": [{"type": "text", "text": user_text}]}
        )
        calls, usage = [], {}
        while True:
            steps = self._next_steps(on_event, usage)
            self.history.extend(steps)
            requested = [s for s in steps if s.get("type") == "function_call"]
            if not requested:
                text = _text_of(steps) or "(no answer from the model)"
                return Answer(text, calls, usage=usage)
            for call in requested:
                if len(calls) >= self.settings.max_tool_calls:
                    answer = self._stop_at_limit(requested, call, calls)
                    answer.usage = usage
                    return answer
                args = call.get("arguments") or {}
                tell("tool_start", {"name": call["name"], "args": args})
                result = self.run_tool(call["name"], args)
                tell("tool_result", {"name": call["name"], "args": args, "result": result})
                calls.append(ToolCall(call["name"], args, result))
                self.history.append(_result_step(call, result))

    def _stop_at_limit(self, requested, first_unrun, calls):
        """Answer the calls not run with an error, so the history stays valid, and stop."""
        skipped = requested[requested.index(first_unrun) :]
        for call in skipped:
            self.history.append(_result_step(call, {"error": "tool-call limit reached"}))
        text = TOOL_LIMIT_MESSAGE.format(limit=self.settings.max_tool_calls)
        self.history.append({"type": "model_output", "content": [{"type": "text", "text": text}]})
        return Answer(text, calls, stopped_at_limit=True)


# --- Talk mode: a spoken conversation on the Live API -----------------------------------------
#
# Read 2026-10-12 (google-genai 2.29.0): `client.aio.live.connect(model=..., config=...)` opens a
# stateful session. Microphone audio goes in with `send_realtime_input(audio=Blob(data, mime_type=
# "audio/pcm;rate=16000"))` (16-bit little-endian PCM, mono); the model hears when the speaker
# stops by itself (voice activity detection). `receive()` yields the messages of one model turn
# and stops after it, so it is called again for the next turn. The model's audio arrives as
# 16-bit PCM at 24 kHz in `server_content.model_turn.parts[].inline_data`; transcripts of both
# sides in `input_transcription` / `output_transcription` when switched on in the config. A
# `tool_call` lists function calls (id, name, args); the client runs them and answers with
# `send_tool_response(function_responses=[FunctionResponse(id, name, response)])`.
# - https://ai.google.dev/gemini-api/docs/live
# - https://ai.google.dev/gemini-api/docs/live-guide
# - https://ai.google.dev/gemini-api/docs/live-tools
# - https://ai.google.dev/api/live

DEFAULT_LIVE_MODEL = "gemini-3.8-live"
LIVE_INPUT_MIME = "audio/pcm;rate=16000"
LIVE_OUTPUT_RATE = 24_000  # Hz; the page plays the audio at this rate

VOICE_NOTE = """
Speaking (this conversation is spoken, not written)
- Keep each answer short: two or three sentences. Say numbers plainly, rounded as the rules above
  allow, and never read a table aloud: the full table and the tools' sources are on screen.
- Instead of the "Assumptions and data" section, name the preset you used in a few words.
"""


def live_model(env=None):
    """The Live API model: GEMINI_LIVE_MODEL, else DEFAULT_LIVE_MODEL."""
    env = os.environ if env is None else env
    return env.get("GEMINI_LIVE_MODEL") or DEFAULT_LIVE_MODEL


def live_function_declarations(tools):
    """The typed chat's tool declarations in the Live API's form (same names and JSON Schema)."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "parameters_json_schema": t["parameters"],
        }
        for t in tools
    ]


def live_events(message):
    """One Live API message as plain event dicts, so callers never see the SDK's types.

    Kinds: "heard" {text} (what the user said), "said" {text} (what the model said), "audio"
    {data: PCM bytes}, "tool_calls" {calls: [{id, name, args}]}, "interrupted" (the user spoke
    over the model: drop the audio not yet played) and "turn_complete".
    """
    found = []
    content = message.server_content
    if content:
        if content.input_transcription and content.input_transcription.text:
            found.append({"kind": "heard", "text": content.input_transcription.text})
        if content.model_turn:
            for part in content.model_turn.parts or []:
                if part.inline_data and part.inline_data.data:
                    found.append({"kind": "audio", "data": part.inline_data.data})
        if content.output_transcription and content.output_transcription.text:
            found.append({"kind": "said", "text": content.output_transcription.text})
        if content.interrupted:
            found.append({"kind": "interrupted"})
        if content.turn_complete:
            found.append({"kind": "turn_complete"})
    if message.tool_call and message.tool_call.function_calls:
        calls = [
            {"id": c.id, "name": c.name, "args": dict(c.args or {})}
            for c in message.tool_call.function_calls
        ]
        found.append({"kind": "tool_calls", "calls": calls})
    return found


class LiveSession:
    """An open Live API session: audio and text in, plain event dicts out (see `live_events`)."""

    def __init__(self, session):
        self._session = session

    async def send_audio(self, pcm):
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm, mime_type=LIVE_INPUT_MIME)
        )

    async def send_text(self, text):
        await self._session.send_realtime_input(text=text)

    async def send_tool_results(self, results):
        """Answer tool calls: `results` is a list of (call id, tool name, result dict)."""
        responses = [
            types.FunctionResponse(id=call_id, name=name, response=result)
            for call_id, name, result in results
        ]
        await self._session.send_tool_response(function_responses=responses)

    async def events(self):
        """Every event of the session, turn after turn, until the session ends."""
        while True:
            async for message in self._session.receive():
                for event in live_events(message):
                    yield event


@asynccontextmanager
async def open_live(tools=None, system_prompt=None):
    """A Live API session with the typed chat's tools and system prompt, plus VOICE_NOTE."""
    from airport_agent import tools as toolbox

    declarations = live_function_declarations(
        tools if tools is not None else toolbox.TOOL_DECLARATIONS
    )
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": (system_prompt or SYSTEM_PROMPT) + VOICE_NOTE,
        "tools": [{"function_declarations": declarations}],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }
    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    async with client.aio.live.connect(model=live_model(), config=config) as session:
        yield LiveSession(session)
