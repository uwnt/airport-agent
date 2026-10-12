"""`airport-agent check-facts [--record] [--open-issue]`: watch the sources of the verified facts.

For every verified (✅) row of docs/DOMAIN_NOTES.md and every constraint in data/constraints.yaml
it downloads each source URL once, reduces the page to its visible text (dropping scripts,
menus, footers and date-like strings that change for no reason), and compares a sha256
fingerprint with the one in data/fact_fingerprints.json. The program never edits a fact: a
changed or vanished source is reported (and, with `--open-issue`, filed as one GitHub issue) and
a person re-verifies.

Outcomes per URL: unchanged, changed, gone (404/410 or the host no longer resolves), unreachable
(blocked, timeout, server error: "can't check", never an alarm), new (no stored fingerprint).
A PDF or other non-HTML file is fingerprinted by its bytes, which is coarser: a re-saved PDF alarms.
"""

import hashlib
import json
import os
import re
import socket
import urllib.error
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import yaml

from airport_agent import tools

REPO = Path(__file__).resolve().parents[3]
FINGERPRINTS_PATH = REPO / "data" / "fact_fingerprints.json"
CONSTRAINTS_PATH = REPO / "data" / "constraints.yaml"
ISSUE_TITLE = "Fact source changed"
EXCERPT_CHARS = 2000
TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
# Hosts and servers answer these when they refuse a robot: we could not look, nothing changed.
GONE_STATUS = {404, 410}
SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript"}
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
# Text that changes on every visit or every year, not because a fact did.
NOISE = [
    re.compile(
        r"(last|page)?\s*(updated|modified|reviewed|revised)\s*:?\s*"
        r"(on\s*)?[A-Za-z0-9,/. -]{0,30}\d{4}",
        re.I,
    ),
    re.compile(r"(©|copyright)[^.]{0,60}\d{4}[^.]{0,40}", re.I),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2},? \d{4}\b", re.I
    ),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
]


class Fetched:
    """What one download gave: a status word and, when it worked, the body bytes and type."""

    def __init__(self, status, body=b"", content_type=""):
        self.status = status  # "ok", "gone" or "unreachable"
        self.body = body
        self.content_type = content_type


def fetch(url):
    """Download one URL (one request, browser-like agent, 20 s) and classify the failure."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return Fetched("ok", response.read(), response.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as error:
        return Fetched("gone" if error.code in GONE_STATUS else "unreachable")
    except urllib.error.URLError as error:
        dns_failure = isinstance(error.reason, socket.gaierror)
        return Fetched("gone" if dns_failure else "unreachable")
    except (TimeoutError, OSError):
        return Fetched("unreachable")


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skipping += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skipping:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def normalise_html(html):
    """Visible text with whitespace collapsed and date-like strings removed."""
    parser = _VisibleText()
    parser.feed(html)
    text = " ".join(parser.parts)
    for pattern in NOISE:
        text = pattern.sub(" ", text)
    return " ".join(text.split())


def _is_html(fetched):
    start = fetched.body[:200].lstrip().lower()
    return "html" in fetched.content_type.lower() or start.startswith((b"<!doctype", b"<html"))


def fingerprint(fetched, recorded):
    """The stored form of a download: sha256, a text excerpt, and how it was read."""
    if _is_html(fetched):
        text = normalise_html(fetched.body.decode("utf-8", errors="replace"))
        digest = hashlib.sha256(text.encode()).hexdigest()
        return {
            "sha256": digest,
            "excerpt": text[:EXCERPT_CHARS],
            "kind": "html",
            "recorded": recorded,
        }
    digest = hashlib.sha256(fetched.body).hexdigest()
    return {"sha256": digest, "excerpt": "", "kind": "binary", "recorded": recorded}


def collect_sources(notes_path=None, constraints_path=CONSTRAINTS_PATH):
    """{url: [fact labels]} from the verified notes and the constraints, one entry per URL."""
    notes_path = notes_path or tools.DOMAIN_NOTES_PATH
    sources = {}
    for cells, _, _ in tools.verified_rows(notes_path.read_text(encoding="utf-8")):
        for url in LINK.findall(cells[4]):
            sources.setdefault(url, []).append(f"DOMAIN_NOTES note {cells[0]}")
    constraints = yaml.safe_load(constraints_path.read_text(encoding="utf-8")) or {}
    for code, entries in constraints.items():
        for entry in entries:
            for url in entry.get("sources", []):
                sources.setdefault(url, []).append(f"constraint {code}: {entry['name']}")
    return {url: sorted(set(facts)) for url, facts in sources.items()}


def check_source(url, facts, stored, fetch_fn, today):
    """(outcome, new record or None) for one URL; the old record is `stored` (or None)."""
    fetched = fetch_fn(url)
    if fetched.status != "ok":
        return fetched.status, None
    new = {**fingerprint(fetched, today), "facts": facts}
    if stored is None:
        return "new", new
    return ("unchanged" if new["sha256"] == stored["sha256"] else "changed"), new


def check_all(sources, stored, fetch_fn=fetch, today=None):
    """Check every URL once, in order; returns a list of result dicts."""
    today = today or date.today().isoformat()
    results = []
    for url, facts in sources.items():
        old = stored.get(url)
        outcome, new = check_source(url, facts, old, fetch_fn, today)
        results.append({"url": url, "facts": facts, "outcome": outcome, "old": old, "new": new})
    return results


def _first_difference(old, new, width=300):
    """Old and new text from the first place they differ, a short window each."""
    start = next((i for i, (a, b) in enumerate(zip(old, new, strict=False)) if a != b), 0)
    start = max(0, start - 40)
    return old[start : start + width], new[start : start + width]


def describe_change(result):
    """Plain lines naming the facts and quoting the old and new text of a changed source."""
    lines = [f"- {result['url']} ({result['outcome']})", f"  Facts: {'; '.join(result['facts'])}"]
    if result["outcome"] == "changed" and result["new"]["kind"] == "html":
        before, after = _first_difference(result["old"]["excerpt"], result["new"]["excerpt"])
        lines += [
            f"  Was: {before or '(outside the stored excerpt)'}",
            f"  Now: {after or '(outside the stored excerpt)'}",
        ]
    elif result["outcome"] == "changed":
        lines.append("  A file (not a web page): its bytes changed.")
    return "\n".join(lines)


def format_report(results):
    """The plain report: a count per outcome, then every URL that is not unchanged."""
    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    summary = ", ".join(f"{n} {name}" for name, n in sorted(counts.items()))
    lines = [f"Checked {len(results)} source(s): {summary}."]
    lines += [describe_change(r) for r in results if r["outcome"] != "unchanged"]
    return "\n".join(lines)


def _github(method, path, token, payload=None):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=json.dumps(payload).encode() if payload else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)


def open_issue(results, token, repo, api=_github):
    """File one issue for all changed/gone sources unless one is already open; returns a message."""
    problems = [r for r in results if r["outcome"] in ("changed", "gone")]
    if not problems:
        return "No changed or missing sources: no issue opened."
    open_ones = api("GET", f"/repos/{repo}/issues?state=open&per_page=100", token)
    if any(i["title"].startswith(ISSUE_TITLE) and "pull_request" not in i for i in open_ones):
        return "A fact-source issue is already open: not opening another."
    body = (
        "These sources changed or disappeared since their fingerprint was recorded. "
        "Re-verify each fact against its source; the watch never edits a fact.\n\n"
        + "\n".join(describe_change(r) for r in problems)
        + "\n\n<!-- uwnt:session -->"
    )
    title = f"{ISSUE_TITLE}: {len(problems)} source(s)"
    made = api("POST", f"/repos/{repo}/issues", token, {"title": title, "body": body})
    return f"Opened issue #{made['number']}."


def load_stored(path=FINGERPRINTS_PATH):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def record(results, stored, path=FINGERPRINTS_PATH):
    """Write fresh fingerprints for every URL that was read; keep the rest as they were."""
    merged = {r["url"]: r["new"] for r in results if r["new"]} | {
        url: old
        for url, old in stored.items()
        if url not in {r["url"] for r in results if r["new"]}
    }
    live = {url: merged[url] for url in sorted(merged)}
    path.write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_facts(record_baseline=False, issue=False, fetch_fn=fetch, out=print):
    """Run the watch; returns the results. Never edits a fact."""
    sources = collect_sources()
    stored = load_stored()
    results = check_all(sources, stored, fetch_fn)
    out(format_report(results))
    if record_baseline:
        record(results, stored)
        out(f"Recorded fingerprints in {FINGERPRINTS_PATH.name}.")
    if issue:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPOSITORY", "uwnt/airport-agent")
        out(
            open_issue(results, token, repo) if token else "No GITHUB_TOKEN: report only, no issue."
        )
    return results
