"""Verified facts from docs/DOMAIN_NOTES.md: only rows marked ✅ are stated as fact.

A tool quotes a domain fact only through `domain_facts`, so an unverified note never reaches the
model, and a fact past its review date is marked stale.
"""

import datetime
import re
from pathlib import Path

from airport_agent.tools_helpers import ToolError, _stale_note

# In the source tree the notes sit at the repo root; installed as a package (the Docker image),
# they are found from the working folder (/app), like config/scoring.yaml in scoring_settings.py.
_REPO = Path(__file__).resolve().parents[2]


def _notes_path(repo=_REPO):
    in_repo = repo / "docs" / "DOMAIN_NOTES.md"
    return in_repo if in_repo.exists() else Path("docs/DOMAIN_NOTES.md")


DOMAIN_NOTES_PATH = _notes_path()


def domain_facts(code, path=DOMAIN_NOTES_PATH, today=None):
    """Verified (✅) facts from docs/DOMAIN_NOTES.md whose claim names this airport code.

    Each fact carries `checked` and `review_by` (ISO dates). After `review_by` (`today` defaults
    to the real date) it is also marked `stale` with a note; it is still returned.
    """
    today = today or datetime.date.today()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    facts = []
    for cells, checked, review_by in verified_rows(text):
        # Drop the "(The ... is dropped)" asides: they name figures that failed the check.
        claim = re.sub(r"\s*\(The [^)]*dropped\)", "", cells[1].replace("**", ""))
        if re.search(rf"\b{re.escape(code)}\b", claim):
            fact = {
                "note": int(cells[0]),
                "fact": claim,
                "sources": re.findall(r"\]\((https?://[^)\s]+)\)", cells[4]),
                "checked": checked.isoformat(),
                "review_by": review_by.isoformat(),
            }
            if review_by < today:
                fact["stale"] = True
                fact["stale_note"] = _stale_note(review_by.isoformat())
            facts.append(fact)
    return facts


def verified_rows(text):
    """(cells, checked, review_by) for each verified (✅) row of the notes table.

    A verified row without both dates, or in the old six-column shape, raises ToolError naming
    the row, so a mistake in the notes shows up instead of the fact silently disappearing.
    """
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells[0].isdigit() or not any(c.startswith("✅") for c in cells[5:6]):
            continue
        where = f"docs/DOMAIN_NOTES.md note {cells[0]}"
        if len(cells) != 8:
            raise ToolError(f"{where}: needs the Checked and Review by columns")
        try:
            checked, review_by = (datetime.date.fromisoformat(c) for c in cells[6:8])
        except ValueError:
            raise ToolError(
                f"{where}: Checked and Review by must be dates like 2026-10-11, "
                f"found {cells[6]!r} and {cells[7]!r}"
            ) from None
        if review_by < checked:
            raise ToolError(f"{where}: Review by {review_by} is before Checked {checked}")
        yield cells, checked, review_by
