"""Check an answer's numbers against the tool results it was built from (Step 7).

The system prompt says every number the agent states must come from a tool. This module finds
the numbers in an answer (`numbers_in`) and lists those that appear in no tool result of the
same question (`unsupported_numbers`). A flagged number needs a human look; it is not
automatically wrong (it may be a count the model made of rows it read, or a number from the
user's own question). A number that passes is only known to appear somewhere in the results,
not to be used in the right place.

What counts as a number in an answer:
- Whole numbers and decimals, with thousands commas ("1,234") and an optional "%" or "pp"
  ("percentage points") after them. A leading minus sign is ignored, so "fell 1.2 pp" matches a
  tool's change of -1.2.
- Not counted: dates (2026-10-11, 2019-12), standalone years from 1990 to 2035 ("since 2019"),
  list markers at the start of a line ("1." or "2)"), and digits inside a word or code (KSFO,
  A320, gemini-3). Digits followed by letters ("28L") count as the number (28).
- Cited note numbers ("note 6") are numbers like any other: the tools give each verified fact
  its note number, so a correct citation is found in the results.

When a stated number matches a tool number:
- equal after rounding the tool number to the decimals stated (12.8 matches 12.83; 13 matches
  12.83), comparing sizes without signs;
- for a "%" or "pp" number, also the tool number times 100, since shares come as fractions
  (`value` 0.128) beside their percentage (`value_pct` 12.8);
- tool numbers are every number value in a result, and every number written inside its text
  (a definition's "1,400 miles", a fact's "750 ft").
Whole numbers match loosely (a stated 3 matches any tool number from 2.5 to 3.5), so the check
catches invented figures, not small slips.
"""

import re
from dataclasses import dataclass

_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
_LIST_MARKER = re.compile(r"^(\s*)\d+[.)](?=\s)", re.M)
_NUMBER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:\s?(%|pp\b|percentage points?\b))?"
)
_FIRST_YEAR, _LAST_YEAR = 1990, 2035


@dataclass(frozen=True)
class Stated:
    """One number as the answer wrote it: its text, its value, how many decimals, its unit."""

    text: str
    value: float
    decimals: int
    unit: str  # "", "%" or "pp"


def numbers_in(text):
    """The numbers stated in `text`, in order (see the module notes for what counts)."""
    text = _DATE.sub(" ", text or "")
    text = _LIST_MARKER.sub(r"\1", text)
    found = []
    for match in _NUMBER.finditer(text):
        whole, fraction, unit = match.groups()
        decimals = len(fraction) - 1 if fraction else 0
        value = float(whole.replace(",", "") + (fraction or ""))
        unit = "pp" if unit and unit.startswith(("pp", "percentage")) else (unit or "")
        is_year = not fraction and not unit and "," not in whole and len(whole) == 4
        if is_year and _FIRST_YEAR <= value <= _LAST_YEAR:
            continue
        found.append(Stated(match.group(0).strip(), value, decimals, unit))
    return found


def tool_numbers(results):
    """Every number in the tool results: number values, and numbers written inside text."""
    found = set()

    def walk(node):
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            found.add(abs(float(node)))
        elif isinstance(node, str):
            found.update(n.value for n in numbers_in(node))
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(results)
    return found


def _matches(stated, number):
    tolerance = 0.5 * 10**-stated.decimals + 1e-9
    candidates = [number]
    if stated.unit in ("%", "pp"):
        candidates.append(number * 100)
    return any(abs(c - stated.value) <= tolerance for c in candidates)


def unsupported_numbers(answer_text, tool_results):
    """Numbers in the answer found in no tool result (each once, in order); see module notes.

    `tool_results` is any JSON-like value: one result, or a list of the question's results.
    """
    known = tool_numbers(tool_results)
    flagged, seen = [], set()
    for stated in numbers_in(answer_text):
        if stated.text in seen:
            continue
        seen.add(stated.text)
        if not any(_matches(stated, number) for number in known):
            flagged.append(stated)
    return flagged
