# Adding a data source

For the next developer. A source is one public dataset that turns into numbers on an airport.
Every file named here exists; the worked example is `src/airport_agent/data/bts_enplanements.py`,
the simplest source. Nothing below is run by magic: you add each piece by hand. Paths start at the
repo root: code is under `src/airport_agent/data/`, samples are in the repo-root folder
`data/samples/`, and snapshots are in `data/snapshots/`.

## Where a new source touches the code
1. **A module** `src/airport_agent/data/<name>.py` with the constants `SOURCE`, `URL`,
   `SUMMARY_NAME`, a `fetch_…` function (network) and a pure `summarise` function.
2. **`src/airport_agent/data/build.py`**: a `write_<name>` function (summary plus manifest, no network) and one
   call in `build_cache`. If its rows carry airport codes, add the module to `CODE_SOURCES` so
   every code is checked against OurAirports.
3. **`src/airport_agent/data/refresh.py`**: add the module to `SUMMARIES` (it goes into the snapshot manifest) and
   a line to `rule_text` if the source has a publication lag.
4. **`src/airport_agent/data/metrics.py`**: a field on `Metrics`, its name in `SIGNALS`, the summary name in
   `load_cache`, an `_add_<name>` function, and one call to it next to the other `_add_…` calls.
5. **`config/sources.yaml`**: the source's settings, and its lag under `point_in_time`, with the
   evidence or the assumption behind it. Add `src/airport_agent/data/asof.py` code for the lag if it is a new kind.
6. **`data/samples/`** (repo root): a small real sample, and offline tests in `tests/test_data_sources.py`
   (summarise), `tests/conftest.py` (write it into the sample cache) and
   `tests/test_data_metrics.py` (the value reaches the airport).
7. **`docs/DATA_SOURCES.md`**: an entry with what it gives, what it helps with, what it can't do.
8. **If scored:** a weight in `config/scoring.yaml` and the signal name in `scoring_settings.py`
   (`STRAIN_SIGNALS` or `GROWTH_SIGNAL`, which make up `SCORED_SIGNALS`; a name outside it is
   rejected when the file loads). Context-only numbers like boardings skip this step.
9. **Rebuild and commit the snapshots.** `load_cache` reads every source's summary, and
   `read_summary` raises `CacheMissingError` when a snapshot lacks it, so the three committed
   snapshots in `data/snapshots/` (D17, D21) must be rebuilt with the new source. A published
   version is never overwritten (`store.py` refuses it), so first remove the old folders
   (`git rm -r data/snapshots/<version>`), then run, with the network and any keys the sources need:
   `uv run airport-agent refresh` (the latest data, `latest-YYYY-MM-DD`; remove the old `latest-…`
   folder, since only one is allowed), `uv run airport-agent refresh --as-of 2019-12` and
   `uv run airport-agent refresh --as-of 2021-12`. Then `uv run python scripts/check_snapshots.py`,
   which fails if a snapshot is over 5 MB or an unexpected version is committed. In Docker the same
   is `docker compose run --rm refresh [--as-of YYYY-MM]`.

## Worked example: BTS boardings
- **Fetch** (`fetch_enplanements`): downloads every year of the top-50 list with `get_json`
  and saves the raw rows to the cache folder with `write_json`. It is the only function in the
  module that uses the network.
- **Summarise** (`summarise`): takes the rows, finds the latest year, and returns
  `(year, {airport: {"enplanements": int, "rank": int}})`. It reads nothing and writes nothing.
- **Write** (`build.write_enplanements`): calls `summarise`, then `write_summary` with the source,
  URL and `as_of=str(year)`. `build_cache` calls it after fetching; for an `--as-of` snapshot it
  first drops years with `asof.usable_enplanement_rows` (lag from `bts_enplanements_lag_years`).
- **Test** (`test_enplanements_latest_year`): feeds `data/samples/bts_enplanements_top50.json`
  to `summarise` and checks the year (2023) and ATL's row, and that ANC is absent.
  `conftest.py` writes the same sample into the test cache.
- **Into metrics** (`_add_boardings`): reads the summary, looks the airport up, and builds a
  `Metric` with value, unit, source, as-of year and a note. No row: it sets
  `missing["enplanements"]` with the reason. `test_data_metrics.py` checks `as_of == "2023"`.

## Rules a source must follow
- Every number carries its **source and as-of date** (the `Metric` fields).
- A missing value is **None with a reason** in `missing`, never 0.
- Tests run **offline**, on the sample. Only `fetch_…` functions touch the network.
- Snapshots use only data **published by their date** (D21): give the source a lag and a test.
- The data layer returns **finished measured values**; scoring only ranks them (D16).
- Airport codes the sources disagree on are matched with a note, and codes that still do not
  match are **listed with a reason in the build manifest**, never dropped silently or filled in
  (D19).
- State a domain fact only if it is marked verified in `docs/DOMAIN_NOTES.md` (D14).

## A committed reference table (no fetch, no snapshot)
A table that is published once and rarely changes can be a file in `data/` that the code reads
directly, like `data/constraints.yaml`. `src/airport_agent/data/faa_capacity.py` and
`data/faa_capacity_profiles.yaml` are the example (D27): a module with `SOURCE`, `URL`, `PATH`, a
pure `summarise` that rejects malformed rows by airport, and a `load`. `metrics.py` reads it in
`load_cache` and adds its Metric with the table's own as-of year, so it applies to every snapshot.
There is no `fetch_…`, no `write_<name>` in `build.py` and no refresh; a new edition is a new file.

## Candidates (all unverified until checked)
- **BTS T-100** segment data: seats offered, international traffic. Named in `docs/PLAN.md` as
  the ideal capacity data. Not tried; check access, size and publication lag first.
- **FAA yearly enplanements** for all commercial airports: would fill the airports the BTS top-50
  list lacks (most of New England; `docs/DATA_SOURCES.md`). Not tried; check it has a data download.
- **FAA ASPM**: login-gated and down when checked (`docs/PLAN.md`); not adopted.
- **FAA Terminal Area Forecast**: not adopted. `docs/PLAN.md` found no data download on 2026-10-11;
  a later check (2026-10-12, D30) found yearly zip files of spreadsheets on `taf.faa.gov` (the 2018
  edition, posted February 2019, would suit a 2019 snapshot). The strongest candidate if a forecast
  signal is wanted.

## Reviewer checklist
- [ ] Module has `SOURCE`, `URL`, `SUMMARY_NAME`; only `fetch_…` uses the network
- [ ] `summarise` is pure and covered by a test on a committed sample
- [ ] `write_<name>` and the `build_cache` call exist; codes checked via `CODE_SOURCES` if needed
- [ ] Added to `SUMMARIES` in `src/airport_agent/data/refresh.py`, `load_cache`, `SIGNALS` and `Metrics` in `metrics.py`
- [ ] `_add_<name>` sets source, as-of, and a reason in `missing` instead of 0
- [ ] Lag in `config/sources.yaml` `point_in_time`, with its evidence, and a snapshot test
- [ ] Settings are in `config/sources.yaml`, weights in `config/scoring.yaml`, not in Python
- [ ] `docs/DATA_SOURCES.md` entry written; any new domain fact is verified in `DOMAIN_NOTES.md`
- [ ] Finished measured values come from the data layer, not scoring (D16)
- [ ] Disagreeing or unmatched airport codes are listed with a reason in the manifest (D19)
- [ ] Snapshots `2019-12`, `2021-12` and `latest-…` rebuilt and committed; `scripts/check_snapshots.py` passes
- [ ] `uv run pytest -q` and `scripts/ci-local` pass with no network
