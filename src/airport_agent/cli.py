"""Terminal chat: `python -m airport_agent.cli`.

With GEMINI_API_KEY set, it's a chat with the model: each tool the model runs is printed as a
step, then the answer. `/reset` starts a new conversation, `/quit` (or Ctrl-D) ends it.

Without a key there is no model: the four example questions are offered as fixed choices, plus a
picker (region or codes, and a preset), and the tool results are printed as plain tables with
their sources and dates.
"""

import json
import sys

from airport_agent import tools

FIXED_QUESTIONS = [
    (
        "Which New England airports are the best terminal-expansion candidates?",
        [("rank_airports", {"region": "New England"})],
    ),
    (
        "How do LAX and SNA compare on congestion?",
        [("compare_airports", {"codes": ["LAX", "SNA"]}), ("airport_profile", {"code": "SNA"})],
    ),
    (
        "What share of Anchorage's passenger departures are long-haul?",
        [("long_haul_share", {"code": "ANC"})],
    ),
    (
        "Is there unmet demand at SFO, and why?",
        [("demand_pressure", {"code": "SFO"}), ("airport_profile", {"code": "SFO"})],
    ),
    (
        "How has SFO changed since 2019?",
        [("compare_over_time", {"code": "SFO", "from_version": "2019-12", "to_version": "latest"})],
    ),
]
NO_KEY_HELP = (
    "No GEMINI_API_KEY is set, so there is no model: pick a fixed question instead.\n"
    "(See the README for how to set the key.)"
)


# --- Plain tables for tool results (no model) -----------------------------------------------


def _fmt(value):
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _sources(result):
    """Every (source, as_of) pair found anywhere in a result, in first-seen order."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "source" in node and "as_of" in node:
                pair = (node["source"], node["as_of"])
                if pair not in found:
                    found.append(pair)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(result)
    return [f"  {source}, as of {as_of}" for source, as_of in found]


def _ranking_table(result):
    weights = ", ".join(f"{k} {v:g}%" for k, v in result.get("weights_pct", {}).items())
    lines = [
        f"Preset: {result['preset']} ({weights}). "
        f"National rank out of {result.get('ranked_nationally', '?')} ranked airports.",
        "",
        f"{'#':>3} {'Natl':>4}  {'Airport':<36} {'Score':>5}  "
        f"{'delay':>6} {'cancel':>6} {'fare':>6} {'growth':>6}  {'Friction':<22} Confidence",
    ]
    for row in result["rows"]:
        points = " ".join(
            f"{row['signals'][label].get('points', '-'):>6}"
            for label in ("delay", "cancellations", "fare premium", "growth")
        )
        friction = row["friction"]
        friction_text = (
            "none" if not friction["points"] else f"-{friction['points']:g} {friction['name']}"
        )
        # A stale friction keeps its marker even when the name is cut to fit the column.
        shown = friction_text[:14] + " (stale)" if friction.get("stale") else friction_text[:22]
        lines.append(
            f"{row['rank']:>3} {row['national_rank']:>4}  "
            f"{(row['code'] + ' ' + row['name'])[:36]:<36} {row['score']:>5}  {points}  "
            f"{shown:<22} {row['confidence']}"
        )
    lines.append("Signal columns: points added (percentile x weight); '-' = missing.")
    for row in result["rows"]:
        if row.get("confidence_reasons"):
            lines.append(f"  {row['code']} low confidence: " + "; ".join(row["confidence_reasons"]))
    for n in result.get("not_ranked", []):
        lines.append(f"Not ranked: {n['code']} ({n['reason']})")
    if result.get("note"):
        lines.append(result["note"])
    return lines


def _signal_table(signals):
    lines = [f"  {'Signal':<14} {'Value':>10} {'Pctile':>7}  Unit"]
    for label, s in signals.items():
        if "missing" in s:
            lines.append(f"  {label:<14} {'-':>10} {'-':>7}  missing: {s['missing']}")
        else:
            value = f"{s['value_pct']:g}%" if "value_pct" in s else _fmt(s["value"])
            lines.append(
                f"  {label:<14} {value:>10} {_fmt(s.get('percentile', '-')):>7}  {s['unit']}"
            )
    return lines


def _change_table(result):
    old, new = result["from"], result["to"]
    lines = [f"{result['code']} {result['name']}: {old['version']} -> {new['version']}"]
    for side in (old, new):
        standing = (
            f"score {side['score']:g}, rank {side['rank']} of {side['ranked_count']}"
            if side["score"] is not None
            else side["not_ranked"]
        )
        lines.append(f"  {side['version']:<20} {standing}")
    lines.append(f"  {'Signal':<30} {'From':>10} {'To':>10} {'Change':>10}")
    for name, s in result["signals"].items():
        cells = []
        for side in (s["from"], s["to"]):
            if side is None:
                cells.append("-")
            else:
                cells.append(
                    f"{side['value_pct']:g}%" if "value_pct" in side else _fmt(side["value"])
                )
        if "change_pct_points" in s:
            change = f"{s['change_pct_points']:+g} pts"
        elif "change" in s:
            c = s["change"]  # whole numbers in full: "+g" would print -3665101 as -3.6651e+06
            change = f"{c:+,.0f}" if float(c).is_integer() else f"{c:+g}"
        else:
            change = s.get("note", "changed" if s.get("changed") else "same")
        lines.append(f"  {name:<30} {cells[0]:>10} {cells[1]:>10} {change:>10}")
    return lines


def format_result(name, result):
    """A tool result as plain text lines, ending with its sources and dates."""
    if "error" in result:
        return f"Error: {result['error']}"
    lines = [f"[{name}]"]
    if name in ("rank_airports", "compare_airports"):
        lines += _ranking_table(result)
    elif name == "demand_pressure" and result.get("ranked"):
        lines += [f"{result['code']} {result['name']}", *_signal_table(result["signals"])]
        lines.append(result["summary"])
    elif name == "compare_over_time":
        lines += _change_table(result)
    elif name == "airport_profile":
        lines.append(f"{result['code']} {result['name']} ({result['state']}): {result['scope']}")
        for metric, m in result["metrics"].items():
            value = f"{m['value_pct']:g}%" if "value_pct" in m else _fmt(m["value"])
            lines.append(f"  {metric:<28} {value:>12}  {m['unit']}")
        for metric, reason in result["missing"].items():
            lines.append(f"  {metric:<28} {'-':>12}  missing: {reason}")
        for fact in result["verified_facts"]:
            stale = f" [{fact['stale_note']}]" if fact.get("stale") else ""
            lines.append(
                f"  Verified fact (domain note {fact['note']}, checked {fact['checked']}): "
                f"{fact['fact']}{stale}"
            )
            lines += [f"    {link}" for link in fact["sources"]]
    elif name == "long_haul_share" and result.get("available"):
        share = result["long_haul_share"]
        lines.append(f"{result['code']} {result['name']}: {share['value_pct']:g}% long-haul")
        lines.append(f"  Definition: {result['definition']}")
        lines.append(f"  Counts: {share.get('note', '')}")
        if result.get("threshold_note"):
            lines.append(f"  {result['threshold_note']}")
    else:
        lines.append(json.dumps(result, indent=2, ensure_ascii=False))
    sources = _sources(result)
    if sources:
        lines += ["Sources:", *sources]
    return "\n".join(lines)


def run_fixed(calls, out=print):
    for name, args in calls:
        out(format_result(name, tools.run_tool(name, args)))
        out("")


# --- The two modes --------------------------------------------------------------------------


def _ask(prompt, read):
    try:
        return read(prompt).strip()
    except EOFError:
        return None


def picker(read, out):
    """Ask for a region or codes and a preset; return the tool calls to run."""
    place = _ask("Region (e.g. New England, LA area) or airport codes (e.g. BOS,SFO): ", read)
    if not place:
        return []
    preset = _ask("Preset [balanced / growth-focused / congestion-focused]: ", read) or None
    if "," in place or (len(place) in (3, 4) and place.isalpha() and place.upper() == place):
        return [("rank_airports", {"codes": place.split(","), "preset": preset})]
    return [("rank_airports", {"region": place, "preset": preset})]


def no_key_mode(read=input, out=print):
    out(NO_KEY_HELP)
    while True:
        out("")
        for i, (question, _) in enumerate(FIXED_QUESTIONS, 1):
            out(f"  {i}. {question}")
        out(f"  {len(FIXED_QUESTIONS) + 1}. Rank a region or some airports (picker)")
        choice = _ask("Choose a number (or /quit): ", read)
        if choice is None or choice in ("/quit", "q"):
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(FIXED_QUESTIONS):
            run_fixed(FIXED_QUESTIONS[int(choice) - 1][1], out)
        elif choice == str(len(FIXED_QUESTIONS) + 1):
            run_fixed(picker(read, out), out)
        else:
            out("Please type one of the numbers.")


def chat_mode(session, read=input, out=print):
    out("Ask about US airports for terminal expansion. /reset starts over, /quit ends.")
    while True:
        text = _ask("\nyou> ", read)
        if text is None or text == "/quit":
            return 0
        if not text:
            continue
        if text == "/reset":
            session.reset()
            out("(new conversation)")
            continue
        try:
            answer = session.send(text)
        except Exception as error:  # a network or API failure must not end the chat
            out(f"The model call failed ({type(error).__name__}: {error}). Try again.")
            continue
        for call in answer.tool_calls:
            args = json.dumps(call.args, ensure_ascii=False)
            status = " -> error: " + call.result["error"] if "error" in call.result else ""
            out(f"  step: {call.name}({args}){status}")
        out(f"\nagent> {answer.text}")


def main(argv=None):
    from airport_agent import llm

    if not llm.has_api_key():
        return no_key_mode()
    return chat_mode(llm.ChatSession())


if __name__ == "__main__":
    sys.exit(main())
