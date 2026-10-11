"""Dated snapshots: the point-in-time rule, the data store, refresh and the CI size budget."""

import importlib.util
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from conftest import FETCHED_AT, SAMPLES, load_sample_json

from airport_agent import main
from airport_agent.data import asof, build, ourairports, refresh
from airport_agent.data.cache import CacheMissingError, load_config, read_summary
from airport_agent.data.metrics import airport_metrics, load_cache
from airport_agent.data.store import FileStore, open_store, snapshot_dir

LAGS = load_config()["point_in_time"]


# ---- Point-in-time rule (pure) ----


@pytest.mark.parametrize(
    ("as_of", "month", "quarter"),
    [
        ("2019-12", (2019, 9), (2019, 2)),
        ("2021-12", (2021, 9), (2021, 2)),
        # Jan 2026 arrived on 1 May 2026, so the end of April must not use it.
        ("2026-04", (2025, 12), (2025, 3)),
        # Jul 2026 arrived 21 Sep 2026 and 2026 Q1 on 3 Sep 2026: both usable by end of October.
        ("2026-10", (2026, 7), (2026, 1)),
        # Six months before August is February, mid-quarter: Q1 2026 hasn't ended long enough.
        ("2026-08", (2026, 5), (2025, 4)),
    ],
)
def test_newest_month_and_quarter_published_by_as_of(as_of, month, quarter):
    end = asof.parse_as_of(as_of)
    assert asof.newest_ontime_month(end, LAGS["bts_ontime_lag_days"]) == month
    assert asof.newest_fare_quarter(end, LAGS["dot_fares_lag_months"]) == quarter


def test_month_published_exactly_at_the_lag_is_usable():
    # Sep 2019 ends 30 Sep; 91 days later is 30 Dec 2019, inside December.
    assert asof.newest_ontime_month(date(2019, 12, 30), 91) == (2019, 9)
    assert asof.newest_ontime_month(date(2019, 12, 29), 91) == (2019, 8)


@pytest.mark.parametrize("text", ["2019-13", "2019-1", "2019", "19-12", "latest"])
def test_as_of_must_be_year_and_month(text):
    with pytest.raises(ValueError, match="YYYY-MM"):
        asof.parse_as_of(text)


def test_boardings_only_for_years_published_by_as_of():
    rows = [{"year": str(year)} for year in (2017, 2018, 2019, 2020)]
    usable = asof.usable_enplanement_rows(rows, date(2019, 12, 31), 1)
    assert [row["year"] for row in usable] == ["2017", "2018"]


# ---- What an older snapshot says ----


def test_snapshot_in_2019_has_no_growth(sample_cache):
    fares = load_sample_json("dot_fares_new_england.json")
    rows_2019 = [row for row in fares if row["year"] == "2019"]
    build.write_fares(
        sample_cache, rows_2019, rows_2019, (2019, 1), (2019, 1), load_config(), FETCHED_AT
    )
    bos = airport_metrics("BOS", sample_cache)
    assert bos.growth_vs_2019 is None
    assert bos.missing["growth_vs_2019"] == "this snapshot is the 2019 baseline"
    assert bos.fare_premium is not None and bos.passengers_per_day is not None


def test_old_snapshot_has_no_long_haul_share(sample_cache):
    build.write_opensky_unavailable(sample_cache, load_config(), "2019-12-31", FETCHED_AT)
    anc = airport_metrics("PANC", sample_cache)
    assert anc.long_haul_share is None
    assert anc.missing["long_haul_share"] == (
        "not available for this date (OpenSky free history is short)"
    )
    bos = airport_metrics("BOS", sample_cache)
    assert bos.missing["long_haul_share"] == "computed only for Anchorage (OpenSky)"


def test_no_flights_keeps_the_requested_window(sample_cache):
    # Carried over from the Step 3 review: no flights must not turn the as-of into "no flights".
    csv_path = SAMPLES / "ourairports_us_scheduled.csv"
    coords = ourairports.parse_coordinates(csv_path)
    window = "2026-10-04 to 2026-10-10"
    build.write_opensky(
        sample_cache, [], coords, load_config(), fetched_at=FETCHED_AT, window=window
    )
    anc = airport_metrics("PANC", sample_cache)
    assert anc.missing["long_haul_share"].endswith(f"known destination in {window}")


# ---- Data store ----


@pytest.fixture
def work(tmp_path_factory):
    """A folder apart from `sample_cache` (which is tmp_path), so copies of it can't nest."""
    return tmp_path_factory.mktemp("work")


def make_snapshot(folder, version, as_of, built_at=FETCHED_AT):
    folder.mkdir(parents=True)
    manifest = {"version": version, "as_of": as_of, "built_at": built_at}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def test_store_publish_get_latest(tmp_path):
    store = FileStore(tmp_path / "store")
    assert store.latest() is None
    for version, as_of in [("2021-12", "2021-12-31"), ("2019-12", "2019-12-31")]:
        assert store.publish(make_snapshot(tmp_path / version, version, as_of)) == version
    assert store.latest() == "2021-12"  # newest as-of, not the last published
    assert (store.get("2019-12") / "manifest.json").exists()
    store.publish(make_snapshot(tmp_path / "new", "latest-2026-10-11", "2026-10-11"))
    assert store.latest() == "latest-2026-10-11"


def test_store_publish_refuses_an_existing_version(tmp_path):
    store = FileStore(tmp_path / "store")
    store.publish(make_snapshot(tmp_path / "a", "2019-12", "2019-12-31", "2026-01-01"))
    with pytest.raises(ValueError, match="'2019-12' is already in .*never change"):
        store.publish(make_snapshot(tmp_path / "b", "2019-12", "2019-12-31", "2026-02-02"))
    assert json.loads((store.get("2019-12") / "manifest.json").read_text())["built_at"] == (
        "2026-01-01"
    )
    assert [p.name for p in (tmp_path / "store").iterdir()] == ["2019-12"]


@pytest.mark.parametrize("version", ["../outside", "", None])
def test_store_rejects_bad_versions(tmp_path, version):
    with pytest.raises(ValueError):
        FileStore(tmp_path).get(version)


def test_store_missing_version_and_empty_store(tmp_path):
    store = FileStore(tmp_path)
    with pytest.raises(CacheMissingError, match="No data snapshot '2019-12'"):
        store.get("2019-12")
    with pytest.raises(CacheMissingError, match="airport-agent refresh"):
        snapshot_dir(store=store)


def test_store_latest_skips_publish_leftovers_and_incomplete_folders(tmp_path):
    store = FileStore(tmp_path)
    make_snapshot(tmp_path / "2019-12", "2019-12", "2019-12-31")
    for hidden in (".2026-09.part", ".2026-09.old"):  # a publish in progress or cut short
        make_snapshot(tmp_path / hidden, "2026-09", "2026-09-30")
    incomplete = make_snapshot(tmp_path / "2026-08", "2026-08", "2026-08-31")
    manifest = json.loads((incomplete / "manifest.json").read_text())
    (incomplete / "manifest.json").write_text(json.dumps({**manifest, "files": ["dot_fares.json"]}))
    make_snapshot(tmp_path / "2026-07", "2021-12", "2026-07-31")  # names another version
    assert store.latest() == "2019-12"
    assert store.get(store.latest()).name == "2019-12"
    with pytest.raises(CacheMissingError, match="'2026-08'.*missing dot_fares.json"):
        store.get("2026-08")


@pytest.mark.parametrize(
    ("manifest", "problem"),
    [("{", "can't be read"), ('{"version": "2026-10"}', "no as_of date")],
)
def test_store_skips_a_broken_manifest(tmp_path, caplog, manifest, problem):
    store = FileStore(tmp_path)
    make_snapshot(tmp_path / "2019-12", "2019-12", "2019-12-31")
    (tmp_path / "2026-10").mkdir()
    (tmp_path / "2026-10" / "manifest.json").write_text(manifest, encoding="utf-8")
    assert store.latest() == "2019-12"
    assert "'2026-10'" in caplog.text and problem in caplog.text
    with pytest.raises(CacheMissingError, match=f"'2026-10'.*broken: .*{problem}"):
        store.get("2026-10")


def test_data_store_env_picks_the_store(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_STORE", f"file://{tmp_path}")
    assert open_store().root == tmp_path
    monkeypatch.delenv("DATA_STORE")
    assert open_store().root == Path("data/snapshots")
    for url in ("s3://bucket/snapshots", "github://owner/repo"):
        with pytest.raises(ValueError, match="s3:// and github:// are described"):
            open_store(url)


def test_metrics_read_the_latest_or_a_named_snapshot(monkeypatch, work, sample_cache):
    store = work / "store"
    for version, as_of in [("2019-12", "2019-12-31"), ("2021-12", "2021-12-31")]:
        shutil.copytree(sample_cache, store / version)
        (store / version / "manifest.json").write_text(
            json.dumps({"version": version, "as_of": as_of}), encoding="utf-8"
        )
    build.write_opensky_unavailable(store / "2019-12", load_config(), "2019-12-31")
    monkeypatch.setenv("DATA_STORE", f"file://{store}")
    assert airport_metrics("PANC").long_haul_share is not None  # latest = 2021-12
    assert airport_metrics("PANC", version="2019-12").long_haul_share is None


# ---- refresh (the build itself replaced by the sample summaries: no network) ----


@pytest.fixture
def offline_build(monkeypatch, sample_cache):
    calls = []

    def fake_build(cache_dir, delete_raw=False, out_dir=None, as_of=None):
        calls.append({"delete_raw": delete_raw, "as_of": as_of})
        shutil.copytree(sample_cache, out_dir)

    monkeypatch.setattr(build, "build_cache", fake_build)
    monkeypatch.setenv("RELEASE_SHA", "abc123")
    return calls


def test_refresh_as_of_publishes_a_dated_snapshot(work, offline_build):
    store = FileStore(work / "store")
    version = refresh.refresh("2019-12", work / "cache", store, today=date(2026, 10, 11))
    assert version == "2019-12"
    assert offline_build == [{"delete_raw": True, "as_of": date(2019, 12, 31)}]
    manifest = json.loads((store.get(version) / "manifest.json").read_text())
    assert (manifest["as_of"], manifest["commit"]) == ("2019-12-31", "abc123")
    assert "published by 2019-12-31" in manifest["point_in_time_rule"]
    assert "OurAirports keeps no history" in manifest["sources"]["ourairports"]["note"]
    assert set(manifest["sources"]) == {
        "ourairports",
        "dot_fares",
        "bts_ontime",
        "bts_enplanements",
        "opensky",
    }
    assert "unresolved_codes" in manifest["sources"]["ourairports"]
    assert str(work) not in json.dumps(manifest)  # no machine paths
    assert not (work / "cache" / "staging" / version).exists()


def test_plain_refresh_is_latest(work, offline_build):
    store = FileStore(work / "store")
    version = refresh.refresh(None, work / "cache", store, today=date(2026, 10, 11))
    assert version == "latest-2026-10-11" == store.latest()
    assert offline_build[0]["as_of"] is None
    assert read_summary(store.get(version), "opensky")["data"]["PANC"]["share"] is not None


def test_second_plain_refresh_on_a_day_gets_its_own_version(work, offline_build):
    store = FileStore(work / "store")
    today = date(2026, 10, 11)
    first = refresh.refresh(None, work / "cache", store, today=today)
    built_first = (store.get(first) / "manifest.json").read_bytes()
    second = refresh.refresh(None, work / "cache", store, today=today)
    third = refresh.refresh(None, work / "cache", store, today=today)
    assert (first, second, third) == (
        "latest-2026-10-11",
        "latest-2026-10-11-2",
        "latest-2026-10-11-3",
    )
    assert (store.get(first) / "manifest.json").read_bytes() == built_first  # untouched
    assert store.latest() == third  # same as-of date: the one built last


def test_refresh_refuses_an_as_of_already_published(work, offline_build):
    store = FileStore(work / "store")
    refresh.refresh("2019-12", work / "cache", store, today=date(2026, 10, 11))
    with pytest.raises(ValueError, match="'2019-12' is already in"):
        refresh.refresh("2019-12", work / "cache", store, today=date(2026, 10, 11))
    assert len(offline_build) == 1  # refused before building (no downloads)


def test_refresh_refuses_a_future_month(work, offline_build):
    with pytest.raises(ValueError, match="future"):
        refresh.refresh("2027-01", work, FileStore(work), today=date(2026, 10, 11))


def test_cli_refresh(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(refresh, "refresh", lambda *args, **kwargs: seen.append(args))
    assert main(["refresh", "--as-of", "2021-12"]) == 0
    assert seen[0][0] == "2021-12"
    with pytest.raises(SystemExit):
        main(["refresh", "--as-of", "Dec 2021"])
    assert "YYYY-MM" in capsys.readouterr().err


def test_load_cache_reads_a_published_snapshot(work, offline_build):
    store = FileStore(work / "store")
    version = refresh.refresh("2021-12", work / "cache", store, today=date(2026, 10, 11))
    assert "lookup" in load_cache(store.get(version))


# ---- CI size budget ----


def load_check():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_snapshots.py"
    spec = importlib.util.spec_from_file_location("check_snapshots", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_file(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * size)
    return path


def test_budget_passes_three_small_snapshots(tmp_path):
    check = load_check()
    files = [
        write_file(tmp_path / v / "manifest.json", 1000)
        for v in ("2019-12", "2021-12", "latest-2026-10-11")
    ]
    assert check.problems(tmp_path, files) == []


def test_budget_fails_an_oversized_snapshot(tmp_path):
    check = load_check()
    files = [
        write_file(tmp_path / "2019-12" / "a.json", 3 * 1024 * 1024),
        write_file(tmp_path / "2019-12" / "b.json", 3 * 1024 * 1024),
    ]
    assert check.problems(tmp_path, files) == ["2019-12: 6.3 MB, over the 5 MB budget"]


def test_budget_fails_extra_snapshots(tmp_path):
    check = load_check()
    files = [
        write_file(tmp_path / v / "manifest.json", 10)
        for v in ("2020-06", "latest-2026-10-10", "latest-2026-10-11")
    ]
    found = check.problems(tmp_path, files)
    assert any(p.startswith("2020-06: not one of") for p in found)
    assert any(p.startswith("more than one latest") for p in found)
