"""The fact-source watch: no real network, the download and the GitHub API are injected."""

import http.client
import io
import json
import socket
import urllib.error
import urllib.request

import pytest

import airport_agent
from airport_agent.data import fact_watch as fw

URL = "https://example.org/a"
FACTS = ["DOMAIN_NOTES note 2"]


def html(text="The cap is 12.2 million.", foot="Last updated March 3, 2026. © 2026 Example"):
    body = f"<html><body><nav>Menu</nav><p>{text}</p><footer>{foot}</footer></body></html>"
    return fw.Fetched("ok", body.encode(), "text/html")


def run(fetched, stored=None):
    stored = {URL: stored} if stored else {}
    return fw.check_all({URL: FACTS}, stored, lambda url: fetched, today="2026-10-12")[0]


def baseline():
    return run(html())["new"]


def test_unchanged_source_is_silent():
    result = run(html(), baseline())
    assert result["outcome"] == "unchanged"
    assert fw.format_report([result]).count("\n") == 0  # the count line only


def test_footer_date_change_does_not_alarm():
    assert (
        run(html(foot="Last updated June 9, 2027. © 2027 Example"), baseline())["outcome"]
        == "unchanged"
    )


def test_changed_text_reports_old_and_new():
    result = run(html("The cap is 12.5 million."), baseline())
    assert result["outcome"] == "changed"
    report = fw.describe_change(result)
    assert "12.2 million" in report and "12.5 million" in report


def test_404_is_gone_and_403_is_unreachable():
    assert run(fw.Fetched("gone"), baseline())["outcome"] == "gone"
    assert run(fw.Fetched("unreachable"), baseline())["outcome"] == "unreachable"


def test_binary_files_are_fingerprinted_by_bytes():
    pdf = fw.Fetched("ok", b"%PDF-1.4 one", "application/pdf")
    old = run(pdf)["new"]
    assert old["kind"] == "binary"
    assert run(fw.Fetched("ok", b"%PDF-1.4 two", "application/pdf"), old)["outcome"] == "changed"


class FakeApi:
    def __init__(self, open_titles=()):
        self.open_titles = list(open_titles)
        self.created = []

    def __call__(self, method, path, token, payload=None):
        if method == "GET":
            self.search = path
            return {"items": [{"title": t} for t in self.open_titles]}
        self.created.append(payload)
        return {"number": 7}


def changed_result():
    return run(html("The cap is 12.5 million."), baseline())


def test_issue_body_names_the_fact():
    api = FakeApi()
    message = fw.open_issue([changed_result()], "t", "o/r", api=api)
    assert message == "Opened issue #7."
    assert api.created[0]["title"] == "Fact source changed: 1 source(s)"
    assert "DOMAIN_NOTES note 2" in api.created[0]["body"]


def test_no_duplicate_when_one_is_open():
    api = FakeApi(open_titles=["Fact source changed: 2 source(s)"])
    assert "already open" in fw.open_issue([changed_result()], "t", "o/r", api=api)
    assert api.created == []


def test_unreachable_opens_no_issue():
    api = FakeApi()
    unreachable = run(fw.Fetched("unreachable"), baseline())
    assert "no issue" in fw.open_issue([unreachable], "t", "o/r", api=api)
    assert api.created == []


def test_urls_come_from_notes_rows_and_constraints(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text(
        "| 4 | A claim | Used | Look | [Site](https://example.org/n) | ✅ "
        "| 2026-10-11 | 2027-10-11 |\n"
        "| 5 | Open | Used | Look | [Other](https://example.org/x) | ❓ | | |\n"
    )
    constraints = tmp_path / "c.yaml"
    constraints.write_text(
        "XYZ:\n  - name: Cap\n    sources:\n      - https://example.org/n\n      - https://example.org/c\n"
    )
    assert fw.collect_sources(notes, constraints) == {
        "https://example.org/n": ["DOMAIN_NOTES note 4", "constraint XYZ: Cap"],
        "https://example.org/c": ["constraint XYZ: Cap"],
    }


def test_every_committed_source_has_a_stored_fingerprint():
    assert set(fw.collect_sources()) <= set(fw.load_stored())


# --- normalisation keeps the fact, drops only the date phrase -------------------------------


@pytest.mark.parametrize("figure", ["12.2", "14.9"])
def test_revised_cap_text_survives_normalising(figure):
    text = fw.normalise_html(f"<p>Cap revised to {figure} million passengers in 2030</p>")
    assert text == f"Cap revised to {figure} million passengers in 2030"


def test_year_range_is_not_a_date_phrase():
    old = fw.normalise_html("<p>Airport updated its cap to 12.2 million for 2026-2030</p>")
    new = fw.normalise_html("<p>Airport updated its cap to 12.5 million for 2026-2030</p>")
    assert "12.2 million for 2026-2030" in old and old != new


@pytest.mark.parametrize(
    "line", ["Last updated: March 4, 2026", "Page last reviewed 2026-01-05", "© 2024-2026 Port"]
)
def test_date_phrases_are_removed(line):
    assert fw.normalise_html(f"<p>Cap 12.2 million. {line}</p>").startswith("Cap 12.2 million.")
    assert "2026" not in fw.normalise_html(f"<p>x {line}</p>").replace("2026-2030", "")


def test_unclosed_nav_does_not_hide_the_page():
    assert "cap 12.2" in fw.normalise_html("<nav>x<p>cap 12.2</p>")


def test_closed_nav_is_still_dropped():
    assert fw.normalise_html("<nav>Menu</nav><p>cap 12.2</p>") == "cap 12.2"


# --- fetch classifies every failure ---------------------------------------------------------


class FakeResponse:
    headers = {"Content-Type": "text/html"}

    def __init__(self, body=b"<p>hi there</p>", fail=None):
        self.body, self.fail = body, fail

    def read(self):
        if self.fail:
            raise self.fail
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fetch_with(monkeypatch, outcome):
    def fake_urlopen(request, timeout):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return fw.fetch(URL)


def http_error(code):
    return urllib.error.HTTPError(URL, code, "x", {}, io.BytesIO())


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (http_error(403), "unreachable"),
        (http_error(500), "unreachable"),
        (http_error(404), "gone"),
        (http_error(410), "gone"),
        (TimeoutError("slow"), "unreachable"),
        (urllib.error.URLError(socket.gaierror(-3, "Temporary failure")), "unreachable"),
        (urllib.error.URLError(socket.gaierror(-2, "Name not known")), "unreachable"),
        (ConnectionResetError("reset"), "unreachable"),
        (FakeResponse(fail=http.client.IncompleteRead(b"ab")), "unreachable"),
    ],
)
def test_fetch_classifies_failures(monkeypatch, outcome, status):
    assert fetch_with(monkeypatch, outcome).status == status


def test_fetch_returns_text_of_a_200(monkeypatch):
    fetched = fetch_with(monkeypatch, FakeResponse())
    assert fetched.status == "ok"
    assert fw.normalise_html(fetched.body.decode()) == "hi there"


# --- the duplicate check uses search, not one page of issues --------------------------------


def test_duplicate_check_searches_this_repo_for_open_issues_by_title():
    api = FakeApi(open_titles=["Fact source changed: 1 source(s)"])
    fw.open_issue([changed_result()], "t", "o/r", api=api)
    assert "/search/issues" in api.search
    for part in ("repo%3Ao/r", "is%3Aopen", "in%3Atitle"):
        assert part in api.search


# --- record / accept / prune ----------------------------------------------------------------

OLD, NEW_URL = "https://example.org/old", "https://example.org/new"


def three_results():
    changed = run(html("The cap is 12.5 million."), baseline())
    fresh = {"url": NEW_URL, "facts": FACTS, "outcome": "new", "old": None, "new": baseline()}
    return [changed, fresh]


def test_record_stores_new_only_and_prunes_uncited(tmp_path):
    path = tmp_path / "f.json"
    results = three_results()
    stored = {URL: results[0]["old"], OLD: {"sha256": "x"}}
    new, accepted, pruned = fw.record(results, stored, path=path)
    saved = json.loads(path.read_text())
    assert (new, accepted, pruned) == ([NEW_URL], [], [OLD])
    assert saved[URL] == stored[URL] and NEW_URL in saved and OLD not in saved


def test_changed_url_is_stored_only_when_accepted(tmp_path):
    path = tmp_path / "f.json"
    results = three_results()
    stored = {URL: results[0]["old"]}
    _, accepted, _ = fw.record(results, stored, accept=[URL], path=path)
    assert accepted == [URL]
    assert json.loads(path.read_text())[URL]["sha256"] == results[0]["new"]["sha256"]


# --- check_facts, _github and the command line, with no network -----------------------------


@pytest.fixture
def watch(monkeypatch, tmp_path):
    path = tmp_path / "fp.json"
    path.write_text(json.dumps({URL: baseline()}))
    monkeypatch.setattr(fw, "FINGERPRINTS_PATH", path)
    monkeypatch.setattr(fw, "collect_sources", lambda: {URL: FACTS})
    monkeypatch.setattr(fw, "fetch", lambda url: html("The cap is 12.5 million."))
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    return path


def test_check_facts_reports_and_leaves_file_alone(watch):
    lines = []
    before = watch.read_text()
    results = fw.check_facts(out=lines.append)
    assert results[0]["outcome"] == "changed" and "changed" in lines[0]
    assert watch.read_text() == before


def test_check_facts_accept_rewrites_only_that_url(watch):
    lines = []
    fw.check_facts(accept=[URL], out=lines.append)
    assert json.loads(watch.read_text())[URL]["sha256"] != baseline()["sha256"]
    assert any("accepted" in line for line in lines)


def test_check_facts_opens_one_issue_through_the_api(watch, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    api = FakeApi()
    lines = []
    fw.check_facts(issue=True, out=lines.append, api=api)
    assert lines[-1] == "Opened issue #7." and len(api.created) == 1


def test_open_issue_flag_without_github_token_opens_nothing(watch, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    assert airport_agent.main(["check-facts", "--open-issue"]) == 0
    assert "No GITHUB_TOKEN" in capsys.readouterr().out and calls == []


def test_api_error_is_one_plain_line_and_nonzero_exit(watch, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")

    def refuse(request, timeout):
        raise http_error(401)

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert airport_agent.main(["check-facts", "--open-issue"]) == 1
    shown = capsys.readouterr()
    assert "secret-value" not in shown.out + shown.err
    assert "Traceback" not in shown.err and shown.err.count("\n") == 1


def test_github_helper_sends_bearer_header_and_json(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["request"] = request
        return FakeResponse(b'{"number": 3}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    reply = fw._github("POST", "/repos/o/r/issues", "abc", {"title": "t"})
    request = seen["request"]
    assert reply == {"number": 3}
    assert request.full_url == "https://api.github.com/repos/o/r/issues"
    assert request.get_header("Authorization") == "Bearer abc"
    assert json.loads(request.data) == {"title": "t"} and request.get_method() == "POST"
