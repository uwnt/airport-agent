"""The fact-source watch: no real network, the download and the GitHub API are injected."""

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
            return [{"title": t} for t in self.open_titles]
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
