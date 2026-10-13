"""Evaluation run (Step 7): ask the real agent a fixed set of questions and write what happened.

Run: doppler run -- uv run python scripts/evaluate.py --model gemini-3.8-flash \\
         --out docs/examples/flash

Release check: `--check` asks the same questions, writes no files, prints PASS or FAIL per
conversation and exits 1 if any fails, or if no conversation was run. A conversation passes when
every question got an answer (no error, no stop at the tool-call limit, not empty) and every number
in every answer was found in a tool result (the number check below). The Deploy workflow runs it
before a production deploy.

Each conversation is a fresh chat; a follow-up question goes to the same chat. For each one a
Markdown transcript is written: the questions, every tool call (arguments, the key numbers, and
the full result folded away), the answer, seconds taken, tokens, cost in US dollars, and the
number check (numbers in the answer that no tool result gave; see airport_agent.number_check).
A README.md in the same folder has one row per conversation and the average cost per question.

The questions are the four example questions (as the chat offers them) plus traps: an airport
the data doesn't cover, a code that isn't an airport, an out-of-scope question, a region switch
in a follow-up, and an ambiguous place name. Answers are written as the model gave them: this
run is evidence, so nothing here tries to make them look better.

Cost = input tokens x input price + (output + thinking tokens) x output price, from PRICES. It is
given twice: with the token counts the API reports, and estimated with tool results, since the
reported input count seems to leave them out (COST_CAVEAT). For the estimate, ToolResultMeter
counts, before each model call, the tokens of every tool result already in the conversation (the
API's token counter, `GeminiClient.count_tokens`) and adds them to the input: each model call
resends the whole history, so a tool result is billed again on every later call.
"""

import argparse
import dataclasses
import datetime
import json
import re
import sys
import time
from pathlib import Path

from airport_agent.llm import (
    NO_ANSWER_TEXT,
    ChatSession,
    GeminiClient,
    add_usage,
    settings_from_env,
)
from airport_agent.number_check import unsupported_numbers

# (file name, questions in one chat). The first four are the chat's example questions.
CONVERSATIONS = [
    ("a-new-england", ["Which New England airports are the best terminal-expansion candidates?"]),
    ("b-lax-vs-sna", ["How do LAX and SNA compare on congestion?"]),
    ("c-anchorage-long-haul", ["What share of Anchorage's passenger departures are long-haul?"]),
    ("d-sfo-unmet-demand", ["Is there unmet demand at SFO, and why?"]),
    ("e-trap-uncovered-airport", ["How promising is San Juan (SJU) for terminal expansion?"]),
    ("f-trap-nonsense-code", ["Rank XQZ against BOS."]),
    ("g-trap-roi-in-dollars", ["What's the ROI in dollars of expanding BOS's terminal?"]),
    (
        "h-trap-region-switch",
        ["Rank the New England airports.", "Now do the same for the LA area."],
    ),
    ("i-trap-ambiguous-place", ["How congested is LA?"]),
]

# US dollars per million tokens. Output includes thinking tokens. Source:
# https://ai.google.dev/gemini-api/docs/pricing (checked 2026-10-11).
# Each model: (last day the price applies, or None for open-ended, input, output), in order.
PRICES_CHECKED = "2026-10-11"
PRICES_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
PRICES = {
    "gemini-3.8-flash": [
        (datetime.date(2026, 12, 31), 0.75, 3.75),
        (None, 1.50, 7.50),
    ],
    # Prompts up to 200k tokens (all of ours are far below).
    "gemini-3.1-pro-preview": [(None, 2.00, 12.00)],
}

COST_CAVEAT = (
    "Reported: the token counts the API reports. Checked 2026-10-11, the reported input count "
    "hardly grows when a tool result is sent back (a ranking result of about 11,000 characters "
    "added 27 input tokens), so tool results seem not to be counted. Estimated with tool "
    "results: before each model call, every tool result already in the conversation is counted "
    "with the API's token counter and added to that call's input, because each model call "
    "resends the whole conversation, so a tool result is billed again on every later call "
    "(a follow-up question included). It is an estimate: the result is counted as plain text, "
    "without the framing around it. No cache discount is applied to either."
)

_LOCAL_PATH = re.compile(r"(?<![\w:/.])/(?:root|home|tmp|Users|var|opt|srv|mnt)/[^\s\"'`)<>]*")


def scrub(text):
    """The text with any absolute local file path replaced, so transcripts can be published."""
    return _LOCAL_PATH.sub("<local path>", text)


def price_per_million(model, on):
    """(input, output) dollars per million tokens for `model` on date `on`; None if unknown."""
    for last_day, price_in, price_out in PRICES.get(model, []):
        if last_day is None or on <= last_day:
            return price_in, price_out
    return None


def cost_usd(model, usage, on):
    """The cost of `usage` (token counts) in dollars, or None if the model or usage is unknown."""
    prices = price_per_million(model, on)
    if prices is None or not usage:
        return None
    output = usage.get("total_output_tokens", 0) + usage.get("total_thought_tokens", 0)
    return (usage.get("total_input_tokens", 0) * prices[0] + output * prices[1]) / 1e6


def money(cost):
    return "unknown" if cost is None else f"${cost:.4f}"


def with_tool_results(usage, tool_result_tokens):
    """`usage` with the estimated tool-result tokens added to its input; None if not known."""
    if tool_result_tokens is None or not usage:
        return None
    total = dict(usage)
    total["total_input_tokens"] = total.get("total_input_tokens", 0) + tool_result_tokens
    return total


def estimated_cost(model, usage, tool_result_tokens, on):
    """The cost with tool results counted in the input (see COST_CAVEAT); None if unknown."""
    usage = with_tool_results(usage, tool_result_tokens)
    return None if usage is None else cost_usd(model, usage, on)


class ToolResultMeter:
    """Wraps a model client; before each call, adds up the tokens of the tool results it resends.

    `count_tokens(text)` -> int counts one text (the API's counter in a real run); each distinct
    text is counted once. `tool_result_tokens` is the running total over every call so far, or
    None once a count has failed (a rate limit or a network error): the estimate is then
    unknown, but the answer goes on.
    """

    def __init__(self, client, count_tokens):
        self.client, self.count_tokens = client, count_tokens
        self._total, self._counted, self.count_failed = 0, {}, False

    @property
    def tool_result_tokens(self):
        return None if self.count_failed else self._total

    @property
    def last_usage(self):
        return getattr(self.client, "last_usage", None)

    def next_steps(self, history, *args, **kwargs):
        for step in history:
            if step.get("type") == "function_result":
                for part in step.get("result") or []:
                    self._add(part.get("text") or "")
        return self.client.next_steps(history, *args, **kwargs)

    def _add(self, text):
        if self.count_failed:
            return
        if text not in self._counted:
            try:
                self._counted[text] = self.count_tokens(text)
            except Exception:  # the estimate becomes unknown; the answer must not fail
                self.count_failed = True
                return
        self._total += self._counted[text]


# --- Running the questions --------------------------------------------------------------------


def _metered(chat):
    """The chat's tool-result token total so far, or None if its client isn't metered."""
    return getattr(chat.client, "tool_result_tokens", None)


def _difference(after, before):
    """after - before, or None if either is unknown."""
    return None if after is None or before is None else after - before


def run_conversation(chat, questions):
    """Ask each question in the same chat; one dict per question with what happened."""
    turns, results_so_far = [], []
    for question in questions:
        started = time.perf_counter()
        metered_before = _metered(chat)
        try:
            answer = chat.send(question)
        except Exception as error:  # the run goes on; the transcript shows the failure
            turns.append(
                {
                    "question": question,
                    "error": f"{type(error).__name__}: {error}",
                    "seconds": time.perf_counter() - started,
                    "calls": [],
                    "usage": {},
                    "tool_result_tokens": None,
                    "text": "",
                    "unsupported": [],
                    "stopped_at_limit": False,
                }
            )
            continue
        seconds = time.perf_counter() - started
        results_so_far += [c.result for c in answer.tool_calls]
        # A follow-up may quote an earlier answer's tool results, so all so far count.
        unsupported = [n.text for n in unsupported_numbers(answer.text, results_so_far)]
        turns.append(
            {
                "question": question,
                "seconds": seconds,
                "calls": answer.tool_calls,
                "usage": answer.usage,
                "tool_result_tokens": _difference(_metered(chat), metered_before),
                "text": answer.text,
                "unsupported": unsupported,
                "stopped_at_limit": answer.stopped_at_limit,
            }
        )
    return turns


# --- Writing it down --------------------------------------------------------------------------


def _row_line(row):
    friction = row.get("friction") or {}
    penalty = f", friction -{friction['points']:g}" if friction.get("points") else ""
    return (
        f"#{row['rank']} {row['code']} score {row['score']} "
        f"(national #{row['national_rank']}, {row['confidence']} confidence{penalty})"
    )


def summarize(name, result):
    """A few plain lines with a tool result's key numbers."""
    if "error" in result:
        return [f"error: {result['error']}"]
    if name in ("rank_airports", "compare_airports"):
        lines = [
            f"preset {result.get('preset')}, weights {result.get('weights_pct')}, "
            f"{result.get('ranked_count')} ranked nationally"
        ]
        lines += [_row_line(row) for row in result.get("rows", [])]
        lines += [f"not ranked: {n['code']} ({n['reason']})" for n in result.get("not_ranked", [])]
        return lines
    if name == "airport_profile":
        facts = [f["note"] for f in result.get("verified_facts", [])]
        return [
            f"{result['code']} {result['name']}: {result['scope']}",
            "measured: " + ", ".join(result.get("metrics", {})),
            f"verified facts (notes): {facts or 'none'}",
        ]
    if name == "long_haul_share":
        if not result.get("available"):
            return [f"{result.get('code')}: {result.get('reason')}"]
        share = result["long_haul_share"]
        return [
            f"{result['code']}: {share.get('value_pct')}% over {result['threshold_miles']:,} "
            f"miles ({share['source']}, {share['as_of']})"
        ]
    if name == "compare_over_time":
        before, after = result["from"], result["to"]
        return [
            f"{result['code']}: {before['version']} score {before['score']} rank "
            f"{before['rank']} -> {after['version']} score {after['score']} rank {after['rank']}"
            f", score change {result.get('score_change')}"
        ]
    if name == "demand_pressure":
        if not result.get("ranked"):
            return [f"{result.get('code')}: not ranked ({result.get('reason')})"]
        return [result["summary"]] + [
            f"{label}: percentile {s.get('percentile', '-')}, value {s.get('value', '-')}"
            for label, s in result["signals"].items()
        ]
    return [", ".join(result)]


def _tokens(usage):
    return (
        f"{usage.get('total_input_tokens', 0):,} in / {usage.get('total_output_tokens', 0):,} "
        f"out / {usage.get('total_thought_tokens', 0):,} thinking"
    )


def _count(tokens):
    return "unknown" if tokens is None else f"{tokens:,}"


def _sum_known(values):
    """The sum, or None if any value is None."""
    values = list(values)
    return None if any(v is None for v in values) else sum(values)


def transcript(name, model, turns, on):
    """One conversation as Markdown."""
    lines = [f"# {name}", "", f"Model: `{model}`. Run on {on.isoformat()}.", ""]
    for number, turn in enumerate(turns, 1):
        lines += [f"## Question {number}", "", f"> {turn['question']}", ""]
        lines += [f"### Tool calls ({len(turn['calls'])})", ""]
        if not turn["calls"]:
            lines += ["None.", ""]
        for i, call in enumerate(turn["calls"], 1):
            args = json.dumps(call.args, ensure_ascii=False)
            lines += [f"{i}. `{call.name}` {args}", ""]
            lines += [f"   - {line}" for line in summarize(call.name, call.result)]
            full = json.dumps(call.result, ensure_ascii=False, indent=2)
            lines += ["", "   <details><summary>Full result</summary>", ""]
            lines += ["   ```json", *[f"   {x}" for x in full.splitlines()], "   ```", ""]
            lines += ["   </details>", ""]
        lines += ["### Answer", ""]
        if turn.get("error"):
            lines += [f"The model call failed: {turn['error']}", ""]
        else:
            lines += [turn["text"], ""]
        if turn["stopped_at_limit"]:
            lines += ["(Stopped at the tool-call limit.)", ""]
        flagged = turn["unsupported"]
        check = (
            "all numbers found in tool results"
            if not flagged
            else f"{len(flagged)} not found in tool results (need a look): " + ", ".join(flagged)
        )
        lines += [
            "### Run",
            "",
            f"- Seconds: {turn['seconds']:.1f}",
            f"- Tokens (reported): {_tokens(turn['usage'])}",
            f"- Tool-result input tokens (estimated): {_count(turn['tool_result_tokens'])}",
            f"- Cost (reported): {money(cost_usd(model, turn['usage'], on))}",
            "- Cost (estimated with tool results): "
            f"{money(estimated_cost(model, turn['usage'], turn['tool_result_tokens'], on))}",
            f"- Number check: {check}",
            "",
        ]
    return scrub("\n".join(lines))


def index(model, settings, rows, on):
    """The folder's README.md: one row per conversation, and the average cost per question."""
    lines = [
        f"# Evaluation run: `{model}`",
        "",
        f"Run on {on.isoformat()} with `scripts/evaluate.py`: thinking level "
        f"{settings.thinking_level}, at most {settings.max_tool_calls} tool calls per question. "
        "Each conversation is a fresh chat; the answers are as the model gave them.",
        "",
        "| Conversation | Questions | Seconds | Tool calls | Tokens reported (in / out / "
        "thinking) | Tool-result input tokens (estimated) | Cost reported (USD) "
        "| Cost estimated with tool results (USD) | Numbers not found in tool results |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    costs, estimates, questions = [], [], 0
    for name, turns in rows:
        usage = {}
        for turn in turns:
            add_usage(usage, turn["usage"])
        tool_tokens = _sum_known(t["tool_result_tokens"] for t in turns)
        cost = cost_usd(model, usage, on)
        estimate = estimated_cost(model, usage, tool_tokens, on)
        costs.append(cost)
        estimates.append(estimate)
        questions += len(turns)
        flagged = sum(len(t["unsupported"]) for t in turns)
        failed = sum(1 for t in turns if t.get("error"))
        lines.append(
            f"| [{name}]({name}.md) | {len(turns)}"
            + (f" ({failed} failed)" if failed else "")
            + f" | {sum(t['seconds'] for t in turns):.1f} | {sum(len(t['calls']) for t in turns)}"
            f" | {_tokens(usage)} | {_count(tool_tokens)} | {money(cost)} | {money(estimate)}"
            f" | {flagged} |"
        )
    lines.append("")
    for label, values in (("reported", costs), ("estimated with tool results", estimates)):
        total = _sum_known(values)
        average = total / questions if total is not None and questions else None
        lines.append(
            f"Average cost per question, {label}: {money(average)} "
            f"(total {money(total)}, {questions} questions)."
        )
    lines += [
        "",
        f"Prices: {PRICES_SOURCE}, checked {PRICES_CHECKED}. Cost = input tokens x input price "
        "+ (output + thinking tokens) x output price.",
        "",
        COST_CAVEAT,
        "",
        "Numbers not found in tool results: numbers in the answer that appear in none of the "
        "conversation's tool results, allowing for rounding and for shares quoted as "
        "percentages. Each needs a human look; it is not automatically wrong.",
        "",
    ]
    return scrub("\n".join(lines))


# --- Command line -----------------------------------------------------------------------------


def check_failure(turns):
    """Why a conversation fails the release check, or None if it passes (no model judges this)."""
    for turn in turns:
        if turn.get("error"):
            return f"model call failed: {turn['error']}"
        if turn["stopped_at_limit"]:
            return "stopped at the tool-call limit without an answer"
        if turn["text"].strip() in ("", NO_ANSWER_TEXT):
            return "no answer from the model"
    flagged = [n for turn in turns for n in turn["unsupported"]]
    if flagged:
        return "numbers not found in tool results: " + ", ".join(flagged)
    return None


def run_check(make_chat, only=None):
    """Run the conversations, print PASS or FAIL for each; 0 if all pass, else 1."""
    failed = total = 0
    for name, questions in CONVERSATIONS:
        if only is not None and name not in only:
            continue
        total += 1
        reason = check_failure(run_conversation(make_chat(), questions))
        failed += reason is not None
        print(f"FAIL {name} \u2014 {reason}" if reason else f"PASS {name} \u2014 ok", flush=True)
    print(f"{total - failed} of {total} conversations passed", flush=True)
    if not total:
        print(f"FAIL no conversation matched --only {' '.join(only or [])}", flush=True)
    return 1 if failed or not total else 0


def main(argv=None, make_chat=None, today=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", help="Gemini model name (default: the app's default)")
    parser.add_argument("--out", type=Path, help="folder for the transcripts")
    parser.add_argument("--check", action="store_true", help="release check: no files, exit code")
    parser.add_argument("--only", nargs="*", help="run only these conversations (file names)")
    args = parser.parse_args(argv)
    if not args.check and not (args.model and args.out):
        parser.error("--model and --out are required unless --check is given")
    settings = settings_from_env()
    if args.model:
        settings = dataclasses.replace(settings, model=args.model)
    if make_chat is None:

        def make_chat():
            client = GeminiClient(settings)
            return ChatSession(
                client=ToolResultMeter(client, client.count_tokens), settings=settings
            )

    if args.check:
        return run_check(make_chat, args.only)
    on = today or datetime.date.today()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, questions in CONVERSATIONS:
        if args.only and name not in args.only:
            continue
        print(f"{name} ...", flush=True)
        turns = run_conversation(make_chat(), questions)
        (args.out / f"{name}.md").write_text(
            transcript(name, args.model, turns, on), encoding="utf-8"
        )
        rows.append((name, turns))
        for turn in turns:
            estimate = estimated_cost(args.model, turn["usage"], turn["tool_result_tokens"], on)
            print(
                f"  {turn['seconds']:.1f} s, {len(turn['calls'])} tool calls, "
                f"{money(cost_usd(args.model, turn['usage'], on))} reported, "
                f"{money(estimate)} estimated with tool results, "
                f"{len(turn['unsupported'])} numbers not found"
                + (f", FAILED: {turn['error']}" if turn.get("error") else ""),
                flush=True,
            )
    (args.out / "README.md").write_text(index(args.model, settings, rows, on), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
