"""Evaluation run (Step 7): ask the real agent a fixed set of questions and write what happened.

Run: doppler run -- uv run python scripts/evaluate.py --model gemini-3.8-flash \\
         --out docs/examples/flash

Each conversation is a fresh chat; a follow-up question goes to the same chat. For each one a
Markdown transcript is written: the questions, every tool call (arguments, the key numbers, and
the full result folded away), the answer, seconds taken, tokens, cost in US dollars, and the
number check (numbers in the answer that no tool result gave; see airport_agent.number_check).
A README.md in the same folder has one row per conversation and the average cost per question.

The questions are the four example questions (as the chat offers them) plus traps: an airport
the data doesn't cover, a code that isn't an airport, an out-of-scope question, a region switch
in a follow-up, and an ambiguous place name. Answers are written as the model gave them: this
run is evidence, so nothing here tries to make them look better.

Cost = input tokens x input price + (output + thinking tokens) x output price, from PRICES, using
the token counts the API reports. See COST_CAVEAT: those counts look too low for the input.
"""

import argparse
import dataclasses
import datetime
import json
import re
import sys
import time
from pathlib import Path

from airport_agent.llm import ChatSession, add_usage, settings_from_env
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
    "The token counts are those the API reports. Checked 2026-10-11: the reported input count "
    "hardly grows when a tool result is sent back (a ranking result of about 11,000 characters "
    "added about 30 input tokens), so tool results seem not to be counted, and the real input "
    "cost may be higher than shown. No cache discount is applied."
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


# --- Running the questions --------------------------------------------------------------------


def run_conversation(chat, questions):
    """Ask each question in the same chat; one dict per question with what happened."""
    turns, results_so_far = [], []
    for question in questions:
        started = time.perf_counter()
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
            f"- Tokens: {_tokens(turn['usage'])}",
            f"- Cost: {money(cost_usd(model, turn['usage'], on))}",
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
        "| Conversation | Questions | Seconds | Tool calls | Tokens (in / out / thinking) "
        "| Cost (USD) | Numbers not found in tool results |",
        "|---|---|---|---|---|---|---|",
    ]
    total_cost, questions, cost_known = 0.0, 0, True
    for name, turns in rows:
        usage = {}
        for turn in turns:
            add_usage(usage, turn["usage"])
        cost = cost_usd(model, usage, on)
        cost_known = cost_known and cost is not None
        total_cost += cost or 0.0
        questions += len(turns)
        flagged = sum(len(t["unsupported"]) for t in turns)
        failed = sum(1 for t in turns if t.get("error"))
        lines.append(
            f"| [{name}]({name}.md) | {len(turns)}"
            + (f" ({failed} failed)" if failed else "")
            + f" | {sum(t['seconds'] for t in turns):.1f} | {sum(len(t['calls']) for t in turns)}"
            f" | {_tokens(usage)} | {money(cost)} | {flagged} |"
        )
    average = total_cost / questions if cost_known and questions else None
    lines += [
        "",
        f"Average cost per question: {money(average)} "
        f"(total {money(total_cost if cost_known else None)}, {questions} questions).",
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


def main(argv=None, make_chat=None, today=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="Gemini model name")
    parser.add_argument("--out", required=True, type=Path, help="folder for the transcripts")
    parser.add_argument("--only", nargs="*", help="run only these conversations (file names)")
    args = parser.parse_args(argv)
    settings = dataclasses.replace(settings_from_env(), model=args.model)
    make_chat = make_chat or (lambda: ChatSession(settings=settings))
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
            print(
                f"  {turn['seconds']:.1f} s, {len(turn['calls'])} tool calls, "
                f"{money(cost_usd(args.model, turn['usage'], on))}, "
                f"{len(turn['unsupported'])} numbers not found"
                + (f", FAILED: {turn['error']}" if turn.get("error") else ""),
                flush=True,
            )
    (args.out / "README.md").write_text(index(args.model, settings, rows, on), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
