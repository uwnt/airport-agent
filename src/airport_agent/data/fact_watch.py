"""`airport-agent check-facts [--record] [--open-issue]`: watch the sources of the verified facts.

For every verified (✅) row of docs/DOMAIN_NOTES.md and every constraint in data/constraints.yaml
it downloads each source URL once, reduces the page to its visible text (dropping scripts,
styles, "last updated" dates and copyright years) and compares a sha256
fingerprint with the one in data/fact_fingerprints.json. The program never edits a fact: a
changed or vanished source is reported (and, with `--open-issue`, filed as one GitHub issue) and
a person re-verifies.

Outcomes per URL: unchanged, changed, gone (HTTP 404/410 only), unreachable (blocked, timeout,
DNS or connection error, server error: "can't check", never an alarm), new (no stored fingerprint),
not watched (a page that changes by design, listed in NOT_WATCHED, never downloaded).
A PDF or other non-HTML file is fingerprinted by its bytes, which is coarser: a re-saved PDF alarms.
"""

import hashlib
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
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
PAGE = 100  # comments per GitHub API page
TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
# Hosts and servers answer these when they refuse a robot: we could not look, nothing changed.
GONE_STATUS = {404, 410}
# The two tags whose text a reader never sees. Nothing else is skipped: a false alarm is cheap.
SKIP_TAGS = {"script", "style"}
# Pages that change by design: collected and reported, never downloaded, no fingerprint.
NOT_WATCHED = {
    "https://transtats.bts.gov/PREZIP/": "a download listing that gains a file every month",
}
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
# A missed change costs more than a false alarm, so only two things are removed: a date that
# directly follows a "last updated/modified/reviewed" label, and a copyright mark with its
# year(s). Every other date stays: it may be the fact (an agreement's end date, a curfew year).
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
WEEKDAY = r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?"
ISO = r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?"
DATE = (
    rf"{WEEKDAY}(?:{ISO}|{MONTH}\s+(?:\d{{1,2}},?\s+)?\d{{4}}"
    rf"|\d{{1,2}}\s+{MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}})"
)
LABEL = r"(?:page\s+)?last\s+(?:updated|modified|reviewed)"
NOISE = [
    re.compile(rf"\b{LABEL}\s*:?\s*(?:on\s+)?{DATE}", re.I),
    re.compile(r"(?:©|copyright)\s*(?:\(c\)\s*)?\d{4}(?:\s*[-–]\s*\d{4})?", re.I),
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
    except (OSError, http.client.HTTPException):  # DNS, refused, timeout, cut-off body
        return Fetched("unreachable")


class _VisibleText(HTMLParser):
    def __init__(self, skip_tags):
        super().__init__()
        self.skip_tags = skip_tags
        self.parts = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skipping += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.skipping:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def normalise_html(html):
    """Visible text with whitespace collapsed; label dates and copyright years removed."""
    parser = _VisibleText(SKIP_TAGS)
    parser.feed(html)
    parser.close()
    if parser.skipping:  # an unclosed <script> or <style> would hide the rest: keep everything
        parser = _VisibleText(set())
        parser.feed(html)
        parser.close()
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
        if url in NOT_WATCHED:
            results.append(
                {"url": url, "facts": facts, "outcome": "not watched", "old": old, "new": None}
            )
            continue
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
    if result["outcome"] == "not watched":
        lines[0] = f"- {result['url']} (not watched ({NOT_WATCHED[result['url']]}))"
    elif result["outcome"] == "gone":
        lines.append(
            "  The source is gone (the page no longer exists): re-verify the fact elsewhere."
        )
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
    """File one issue for all changed/gone sources, or comment on the one already open.

    The comment names only the sources the open issue (body and comments) does not name yet.
    Returns a message.
    """
    problems = [r for r in results if r["outcome"] in ("changed", "gone")]
    if not problems:
        return "No changed or missing sources: no issue opened."
    query = urllib.parse.quote(f'repo:{repo} is:issue is:open in:title "{ISSUE_TITLE}"')
    found = api("GET", f"/search/issues?q={query}", token)["items"]
    existing = next((i for i in found if i["title"].startswith(ISSUE_TITLE)), None)
    if existing:
        return _comment_on(existing, problems, token, repo, api)
    body = (
        "These sources changed or disappeared since their fingerprint was recorded. "
        "Re-verify each fact against its source; the watch never edits a fact.\n\n"
        + "\n".join(describe_change(r) for r in problems)
    )
    title = f"{ISSUE_TITLE}: {len(problems)} source(s)"
    made = api("POST", f"/repos/{repo}/issues", token, {"title": title, "body": body})
    return f"Opened issue #{made['number']}."


def _all_comments(number, token, repo, api):
    """Every comment of an issue, read page by page until a short page."""
    comments, page = [], 1
    while True:
        path = f"/repos/{repo}/issues/{number}/comments?per_page={PAGE}&page={page}"
        got = api("GET", path, token)
        comments += got
        if len(got) < PAGE:
            return comments
        page += 1


def _names(text, url):
    """True when `url` appears whole in `text`, not as the start of a longer URL."""
    return re.search(rf"(?<!\w){re.escape(url)}(?![\w/%~#?&=+@:-]|\.\w)", text) is not None


def _is_named(result, issue, comments):
    """Named in the body or a comment written after the URL's stored `recorded` date."""
    since = (result["old"] or {}).get("recorded", "")
    posts = [(issue.get("created_at") or "9999", issue.get("body") or "")]
    posts += [(c.get("created_at") or "9999", c.get("body") or "") for c in comments]
    return any(made[:10] > since and _names(text, result["url"]) for made, text in posts)


def _comment_on(issue, problems, token, repo, api):
    number = issue["number"]
    comments = _all_comments(number, token, repo, api)
    fresh = [r for r in problems if not _is_named(r, issue, comments)]
    if not fresh:
        return f"Issue #{number} is already open and names every changed source: no comment added."
    body = "More sources changed or disappeared since this issue was opened.\n\n" + "\n".join(
        describe_change(r) for r in fresh
    )
    api("POST", f"/repos/{repo}/issues/{number}/comments", token, {"body": body})
    return f"Added a comment to issue #{number} naming {len(fresh)} more source(s)."


def load_stored(path=None):
    path = path or FINGERPRINTS_PATH
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def record(results, stored, accept=(), *, baseline=False, path=None):
    """Re-store the accepted changed URLs; with `baseline` also store new URLs and prune.

    A changed URL is never re-recorded on its own: that would accept a change nobody verified.
    Without `baseline`, nothing but the accepted URLs is touched.
    Returns (recorded, accepted, pruned) as lists of URLs.
    """
    path = path or FINGERPRINTS_PATH
    cited = {r["url"] for r in results if r["outcome"] != "not watched"}
    new = [r["url"] for r in results if r["outcome"] == "new"] if baseline else []
    accepted = [r["url"] for r in results if r["outcome"] == "changed" and r["url"] in accept]
    pruned = sorted(set(stored) - cited) if baseline else []
    fresh = {r["url"]: r["new"] for r in results if r["url"] in new + accepted}
    merged = {url: old for url, old in stored.items() if url not in pruned} | fresh
    live = {url: merged[url] for url in sorted(merged)}
    path.write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return new, accepted, pruned


class IssueError(Exception):
    """The GitHub issue could not be opened; the message is safe to print."""


def check_facts(record_baseline=False, accept=(), issue=False, fetch_fn=None, out=print, api=None):
    """Run the watch; returns the results. Never edits a fact."""
    stored = load_stored()
    results = check_all(collect_sources(), stored, fetch_fn or fetch)
    taken = {r["url"] for r in results if r["outcome"] == "changed" and r["url"] in accept}
    shown = [r for r in results if r["url"] not in taken]  # accepted now: verified, not reported
    out(format_report(shown))
    if record_baseline or accept:
        new, accepted, pruned = record(results, stored, accept, baseline=record_baseline)
        out(
            f"Recorded {len(new)} new, accepted {len(accepted)} changed, "
            f"pruned {len(pruned)} no longer cited, in {FINGERPRINTS_PATH.name}."
        )
        lines = [f"  recorded {u}" for u in new]
        lines += [f"  accepted {u}" for u in accepted] + [f"  pruned {u}" for u in pruned]
        lines += [f"  not changed, ignored: {u}" for u in accept if u not in accepted]
        for line in lines:
            out(line)
    if issue:
        secret = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPOSITORY", "uwnt/airport-agent")
        if not secret:
            out("No GITHUB_TOKEN: report only, no issue.")
        else:
            try:
                out(open_issue(shown, secret, repo, api=api or _github))
            except (OSError, http.client.HTTPException, KeyError, ValueError) as error:
                code = getattr(
                    error, "code", None
                )  # an HTTPError carries the status, never the token
                if code:
                    raise IssueError(f"GitHub API error: HTTP {code}") from None
                raise IssueError(f"Could not open the issue ({type(error).__name__}).") from None
    return results
