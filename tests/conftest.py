"""Shared test setup: no test may use the network, and a data cache built from data/samples/."""

import csv
import io
import json
import shutil
import socket
import tarfile
from pathlib import Path

import pytest

from airport_agent.data import build, ourairports
from airport_agent.data.cache import load_config

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
FETCHED_AT = "2026-10-11T00:00:00+00:00"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to open a network connection."""

    def refuse(*args, **kwargs):
        raise AssertionError("tests must not use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def load_sample_json(name):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def ontime_sample_as_month():
    """The committed July 2026 on-time sample as a monthly summary (counts per airport).

    The sample stores rates, not counts, and has no diverted count, so counts are rebuilt from
    it with diverted = 0: cancelled = rate × arrivals, landed = arrivals − cancelled, and NAS
    minutes = minutes per landed flight × landed.
    """
    month = {}
    with (SAMPLES / "bts_ontime_by_airport_2026_07.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            scheduled = int(row["arrivals"])
            cancelled = round(float(row["cancel_rate"]) * scheduled)
            landed = scheduled - cancelled
            month[row["airport"]] = {
                "scheduled": scheduled,
                "cancelled": cancelled,
                "diverted": 0,
                "landed": landed,
                "nas_delay_minutes": float(row["nas_delay_min_per_landed"]) * landed,
            }
    return month


@pytest.fixture
def sample_cache(tmp_path):
    """A cache directory built only from data/samples/, the way the real build writes it."""
    config = load_config()
    csv_path = SAMPLES / "ourairports_us_scheduled.csv"
    fares = load_sample_json("dot_fares_new_england.json")
    build.write_fares(
        tmp_path,
        [row for row in fares if row["year"] == "2026"],
        [row for row in fares if row["year"] == "2019"],
        (2026, 1),
        (2019, 1),
        config,
        FETCHED_AT,
    )
    build.write_ontime(tmp_path, {(2026, 7): ontime_sample_as_month()}, FETCHED_AT)
    build.write_enplanements(tmp_path, load_sample_json("bts_enplanements_top50.json"), FETCHED_AT)
    # Last, as in the build: it checks every DOT and BTS code against the airport list.
    build.write_airports(tmp_path, ourairports.parse_airports(csv_path), fetched_at=FETCHED_AT)
    build.write_opensky(
        tmp_path,
        load_sample_json("opensky_departures_panc.json"),
        ourairports.parse_coordinates(csv_path),
        config,
        fetched_at=FETCHED_AT,
    )
    return tmp_path


@pytest.fixture(autouse=True)
def no_data_release_check(monkeypatch):
    """The server's startup check for GitHub data releases stays off unless a test turns it on."""
    monkeypatch.setenv("DATA_RELEASES", "off")


@pytest.fixture
def make_snapshot(sample_cache, tmp_path_factory):
    """make_snapshot(version, as_of, root=None) -> a complete snapshot folder of the sample data."""

    def make(version, as_of="2026-10-11", root=None, **manifest):
        folder = Path(root or tmp_path_factory.mktemp("snap")) / version
        shutil.copytree(sample_cache, folder)
        manifest = {"version": version, "as_of": as_of, "files": [], **manifest}
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return folder

    return make


def tar_gz(*entries):
    """A .tar.gz archive (bytes) of (name in the archive, folder or file on disk) pairs."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, path in entries:
            tar.add(path, arcname=name)
    return buffer.getvalue()
