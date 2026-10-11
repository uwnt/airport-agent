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

Settings come from the environment, each with a default:
- GEMINI_API_KEY: the key; without it there is no model (the CLI offers fixed questions instead).
- GEMINI_MODEL: default `gemini-3.8-flash` (Flash tier, stable). A Pro-tier alternative is
  `gemini-3.1-pro-preview` (more careful on multi-tool questions, slower, costs more, preview).
- MAX_ANSWER_TOKENS (default 4096), MAX_TOOL_CALLS per question (default 8),
  REQUEST_TIMEOUT_SECONDS per model call (default 120).
- GEMINI_THINKING_LEVEL: minimal, low, medium or high (default low). Measured 2026-10-11 on one
  question: a call at the model's default level took about 44 s, at low about 11 s.

SDK calls follow Google's docs, read 2026-10-11 (google-genai 2.29.0): the Interactions API,
`client.interactions.create(model=..., input=history, tools=..., system_instruction=...,
generation_config={"max_output_tokens": ..., "thinking_level": ...}, store=False)`; the
response's `steps` include `function_call` steps (id, name, arguments), answered with
`function_result` steps.
- https://ai.google.dev/gemini-api/docs/function-calling
- https://ai.google.dev/gemini-api/docs/models
- https://googleapis.github.io/python-genai/
"""

import json
import os
from dataclasses import dataclass, field

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.8-flash"
PRO_MODEL = "gemini-3.1-pro-preview"
# Retried: short-lived server errors only. Not 429: a spent daily quota comes back as 429 with a
# Retry-After of hours, and the SDK would sleep that long; the user should see the error at once.
RETRY = types.HttpRetryOptions(attempts=3, http_status_codes=[408, 500, 502, 503, 504])

SYSTEM_PROMPT = """\
You help investment analysts judge which US airports are most promising for terminal expansion.
You give decision support, not investment advice.

Numbers
- Every number you state must appear in a tool result from this conversation: a score, rank,
  percentile, points, measured value, value_pct, count, date or weight. Copy it as the tool gave
  it (you may round to fewer decimals, and quote value_pct as a percentage). Never compute a new
  number (no differences, ratios, sums or averages of your own) and never recall one from memory.
  If you need a number no tool gives, say it isn't available.
- Before answering about an airport or region, call the tools; don't answer from memory. For
  "why" questions, call airport_profile (for verified facts) and demand_pressure.

Facts and general knowledge
- Facts about an airport (caps, curfews, runways, history) may be stated as fact only if they are
  in airport_profile's verified_facts; cite the note number and a source link.
- Anything else you add from your own knowledge must be marked "(general knowledge)" and must
  contain no numbers.

Places
- "LA" means LAX, the airport; "LA area" means the Los Angeles region (LAX, SNA, BUR, LGB, ONT).
  Named regions: New England, LA area. A city name means its main airport (Hartford = BDL).
- Only lower-48 airports in the DOT fare data are ranked. Anchorage is not ranked; for it, use
  long_haul_share and airport_profile.
- If a tool returns an error, say so plainly and suggest what you can do instead.

Out of scope
- Cargo economics, financing, airline strategy and construction cost are out of scope: say so in
  one sentence and offer what you can do (rank, compare, profile, demand signals, Anchorage
  long-haul share).

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

    def next_steps(self, history, tools, system_prompt):
        interaction = self.client.interactions.create(
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
        return [step.model_dump(mode="json", exclude_none=True) for step in interaction.steps]


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
    tests pass a fake. `run_tool(name, args)` -> dict runs a tool and never raises.
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

    def send(self, user_text):
        """Answer one user message; returns an Answer with the text and the tools it ran.

        If the model call fails, the history goes back to before this message and the error is
        raised, so the next message starts from a clean conversation.
        """
        start = len(self.history)
        try:
            return self._answer(user_text)
        except Exception:
            del self.history[start:]
            raise

    def _answer(self, user_text):
        self.history.append(
            {"type": "user_input", "content": [{"type": "text", "text": user_text}]}
        )
        calls = []
        while True:
            steps = self.client.next_steps(self.history, self.tools, self.system_prompt)
            self.history.extend(steps)
            requested = [s for s in steps if s.get("type") == "function_call"]
            if not requested:
                return Answer(_text_of(steps) or "(no answer from the model)", calls)
            for call in requested:
                if len(calls) >= self.settings.max_tool_calls:
                    return self._stop_at_limit(requested, call, calls)
                args = call.get("arguments") or {}
                result = self.run_tool(call["name"], args)
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
