# Adding a data source

For the next developer. A source is one public dataset that turns into numbers on an airport.
Every file named here exists; the worked example is `src/airport_agent/data/bts_enplanements.py`,
the simplest source. Nothing below is run by magic: you add each piece by hand.

## Where a new source touches the code
1. **A module** `src/airport_agent/data/<name>.py` with the constants `SOURCE`, `URL`,
   `SUMMARY_NAME`, a `fetch_…` function (network) and a pure `summarise` function.
2. **`data/build.py`**: a `write_<name>` function (summary plus manifest, no network) and one
   call in `build_cache`. If its rows carry airport codes, add the module to `CODE_SOURCES` so
   every code is checked against OurAirports.
3. **`data/refresh.py`**: add the module to `SUMMARIES` (it goes into the snapshot manifest) and
   a line to `rule_text` if the source has a publication lag.
4. **`data/metrics.py`**: a field on `Metrics`, its name in `SIGNALS`, the summary name in
   `load_cache`, an `_add_<name>` function, and one call to it next to the other `_add_…` calls.
5. **`config/sources.yaml`**: the source's settings, and its lag under `point_in_time`, with the
   evidence or the assumption behind it. Add `asof.py` code for the lag if it is a new kind.
6. **`data/samples/`**: a small real sample, and offline tests in `tests/test_data_sources.py`
   (summarise), `tests/conftest.py` (write it into the sample cache) and
   `tests/test_data_metrics.py` (the value reaches the airport).
7. **`docs/DATA_SOURCES.md`**: an entry with what it gives, what it helps with, what it can't do.
8. **If scored:** a weight in `config/scoring.yaml` and the signal name in `scoring.py`
   (`STRAIN_SIGNALS` or `GROWTH_SIGNAL`, which make up `SCORED_SIGNALS`; a name outside it is
   rejected when the file loads). Context-only numbers like boardings skip this step.

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
- State a domain fact only if it is marked verified in `docs/DOMAIN_NOTES.md` (D14).

## Candidates (all unverified until checked)
- **BTS T-100** segment data: seats offered, international traffic. Named in `docs/PLAN.md` as
  the ideal capacity data. Not tried; check access, size and publication lag first.
- **FAA yearly enplanements** for all commercial airports: would fill the airports the BTS top-50
  list lacks (most of New England, Anchorage). Not tried; check it has a data download.
- **FAA ASPM**: login-gated and down when checked (`docs/PLAN.md`); not adopted.
- **FAA Terminal Area Forecast**: no data download found (`docs/PLAN.md`); not adopted.

A plug-in registry (one registration per source) was considered and not chosen: fewer edit
points, but more code for six sources.

## Reviewer checklist
- [ ] Module has `SOURCE`, `URL`, `SUMMARY_NAME`; only `fetch_…` uses the network
- [ ] `summarise` is pure and covered by a test on a committed sample
- [ ] `write_<name>` and the `build_cache` call exist; codes checked via `CODE_SOURCES` if needed
- [ ] Added to `SUMMARIES` in `refresh.py`, `load_cache`, `SIGNALS` and `Metrics` in `metrics.py`
- [ ] `_add_<name>` sets source, as-of, and a reason in `missing` instead of 0
- [ ] Lag in `config/sources.yaml` `point_in_time`, with its evidence, and a snapshot test
- [ ] Settings are in `config/sources.yaml`, weights in `config/scoring.yaml`, not in Python
- [ ] `docs/DATA_SOURCES.md` entry written; any new domain fact is verified in `DOMAIN_NOTES.md`
- [ ] `uv run pytest -q` and `scripts/ci-local` pass with no network
