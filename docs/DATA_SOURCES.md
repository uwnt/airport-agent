# Data sources: what each one can and can't answer

Checked by hand on 2026-10-11 (Step 1). Each source has a spike script in `scripts/spike/` and a
small sample in `data/samples/`, which later serves as an offline test fixture.

The four example questions: **Q1** New England expansion candidates · **Q2** LAX vs SNA congestion ·
**Q3** long-haul share out of Anchorage · **Q4** unmet demand at SFO, and why.

## DOT Consumer Airfare Report, Table 1a
- **Gives:** for each airport pair and quarter (1993 onward per the DOT table documentation; our sample holds only 2019 Q1 and 2026 Q1): passengers per day, average fare,
  distance, the largest carrier and its share.
- **Helps with:** Q1 (volume, growth, fare premium), Q2 and Q4 (volume, growth).
- **Can't:**
  - **No Alaska:** Anchorage has no rows, so Q3 needs OpenSky.
  - **Domestic only:** international passengers are not in it.
  - **Small airports may be undercounted.** The table covers a limited set of markets (DOT table
    documentation; not re-checked), and BTV shows only 253 passengers a day in 2026 Q1 in our
    sample. Treat small-airport totals as a lower bound until checked against another source.
- **Trap found:** compare the same quarter across years. A first run comparing Q4 2019 with
  Q1 2026 made Boston look 24% down (first run, not kept); the committed sample (Q1 2026 vs
  Q1 2019) shows BOS down 10.2%.

## BTS enplanements (top 50 airports)
- **Gives:** boarded passengers per airport per year, 2003–2023, with coordinates.
- **Helps with:** a size check for large airports (BOS, LAX, SFO).
- **Can't:**
  - **Top 50 only:** New England airports other than BOS are missing in recent years.
  - **No Anchorage** in any year.
  - **Stops at 2023.**

## BTS On-Time Performance
- **Gives:** every domestic flight by a reporting airline, with delay minutes split by cause.
  NAS delay is BTS's "National Aviation System" category: delay from the airport and airspace
  system, which (as BTS defines it; to confirm on its definitions page) can include heavy traffic
  and non-extreme weather. Extreme weather is counted separately.
- **Helps with:** congestion for Q2 and Q4. It is the main *measured* congestion signal among the
  free sources we found.
- **Sample (July 2026), flights arriving at each airport:**

  | | SFO | EWR | BOS | ORD | LAX | SNA | ANC |
  |---|---|---|---|---|---|---|---|
  | NAS delay min per landed flight | 15.2 | 13.2 | 9.7 | 8.1 | 2.3 | 2.2 | 1.9 |
  | Cancelled | 1.3% | 8.0% | 5.9% | 4.4% | 1.3% | 1.0% | 0.7% |

  Cancellations here are cancelled ÷ scheduled arrivals. The data layer follows D7 and leaves
  diverted flights out of the denominator, which moves EWR from 8.0% to 8.2%.

- **Can't, or watch out:**
  - **Delay is filed at the arrival airport**, wherever it was caused (origin, en route). So it
    means "delay on flights into SFO", not strictly "delay at SFO".
  - **Cancellations are a separate signal.** Averages divide by flights that landed; the cancel
    rate shows what the delay figure hides (EWR cancels 8% of arrivals).
  - **Doesn't separate LAX from SNA:** both are about 2.2, so Q2 needs a second congestion measure.
  - **One summer month is not a year.**
  - **Large raw files:** each month is a ~32 MB download; we keep only the per-airport summary.
  - **About 2–3 months behind.**
  - **Diverted flights:** the first July 2026 summary counted diverted flights as landed at their
    original destination (effect small; EWR moved from 12.9 to 13.2 when excluded). The script
    and the committed sample now exclude them.

## FAA NAS Status
- **Gives:** delay programs, ground stops and closures, right now.
- **Helps with:** a "current conditions" line in an answer.
- **Can't:** give any history. It can't be used for scoring.
- **Sample gap:** the saved sample has only airport closures, no ground delay or ground stop, so
  tests built on it won't cover those shapes yet. Capture another sample on a day with delays.

## OurAirports
- **Gives:** every airport's codes, type, region and coordinates. 679 US airports have scheduled
  service and an IATA code.
- **Helps with:** every question. It is the code lookup between IATA (DOT uses `SFO`) and ICAO
  (OpenSky uses `KSFO`), and the coordinates give distances for Q3.
- **Watch:**
  - Alaska ICAO codes start with P (Anchorage is `PANC`), so "add a K" is wrong.
  - 70 of the 679 have no `icao_code`; only 18 of those have a four-letter `gps_code`
    (33 have a 3-character local code and 19 have none), so 52 have no four-letter code at all.
    All the airports in our four questions (BOS, LAX, SNA, SFO, ANC, BDL, PVD, MHT, PWM, BTV)
    have one.
  - The list includes 42 seaplane bases and 3 heliports; filter by type when ranking.

## OpenSky Network (free account)
- **Gives:** actual departures and arrivals per airport from transponder data, with an *estimated*
  destination.
- **Helps with:** Q3 (where Anchorage flights go), flights per hour for Q2.
- **Sample:** 552 departures from Anchorage in two days (138 are private aircraft). The sample is
  trimmed to the fields we use, and US private tail numbers (N-numbers) are masked as `PRIVATE`; a few non-US registrations may remain.
- **Can't, or watch out:**
  - **Cargo and private flights are mixed in.** Prefixes like GTI, FDX, CKS, UPS and NAC are
    cargo; callsigns that are a US tail number are private aircraft: after trimming spaces, match
    `^N[0-9][0-9A-Z]{0,4}$` (for example N269TD, N795J). NAC (Northern Air Cargo) starts with N
    but is not matched by this rule. Filter by a fixed passenger-airline list.
  - **Local flying:** 23 flights went from Anchorage back to Anchorage, and 58 of the 63 to nearby
    Kenai (PAEN) are private tail-number aircraft. Exclude same-airport and short hops before
    computing a long-haul share.
  - **Destination unknown for ~14%** of flights.
  - **Terms restrict commercial use** (see decision D5).
  - **No deep history on a free account.**

## FAA Airport Capacity Profiles (2014), Table 1
- **Gives:** for 30 large US airports, the range of aircraft operations an hour the runways can
  handle in visual, marginal and instrument (bad-weather) conditions, from page 9 of the FAA
  report, typed into `data/faa_capacity_profiles.yaml`. We turn it into one signal,
  `bad_weather_capacity_loss`: the share of hourly runway capacity lost in instrument weather
  compared with visual (SFO: instrument 70–72 against visual 100–110 an hour, 32% lost).
- **Helps with:** Q2 and Q4 (is bad weather part of why an airport runs short of room).
- **Can't, or watch out:**
  - **30 airports only;** every other airport shows the signal as missing, with that reason.
  - **From 2014.** Runways and procedures have changed since; the page marks it stale.
  - **Runway capacity, not terminal space.** It says nothing about gates or the terminal.
  - **Shown only, not scored** (decision D27).
  - Where the table has separate arrival-priority and departure-priority rows, we take the lowest
    low to the highest high across both.

## Fact-source watch (`airport-agent check-facts`)
- **Gives:** a re-check of the page behind every verified fact in `docs/DOMAIN_NOTES.md` and every
  constraint in `data/constraints.yaml`. Each URL is downloaded once, reduced to its visible text,
  and a sha256 fingerprint is compared with the one in `data/fact_fingerprints.json`. A changed or
  vanished source is reported. `refresh --check-facts` runs the same report after a refresh. The
  program never edits a fact: a person re-verifies.
- **The rule: a missed change costs more than a false alarm.** A false alarm costs a person a
  minute; a missed change leaves a wrong fact in place. So normalising removes only what is clearly
  not content: the text inside `script` and `style` (if either is left unclosed, the whole page's
  text is kept), a date that directly follows a "last updated / modified / reviewed" or "page last
  ..." label (also with a weekday, "4 March 2026" or an ISO date-time), and a copyright mark with
  its year(s). Menus and footers are kept. Every other date stays, including a bare "updated on"
  date. Whitespace is collapsed; nothing else is removed.
- **Listing pages:** the FAA PFC page, the Alaska airport press releases and the SNA reports page
  can alarm when a new item is posted, because each holds the fact itself. A person looks and
  closes the issue. A possible follow-up: compare each fact's quoted wording instead of the page.
- **Not watched:** a page that changes by design is listed in `NOT_WATCHED` in
  `src/airport_agent/data/fact_watch.py` with its reason, shown as "not watched (reason)", never
  downloaded and given no fingerprint. Today that is the BTS download listing behind note 10 ("a
  download listing that gains a file every month").
- **A new source:** a source with no stored fingerprint shows as "new". The test that every cited
  source has a stored fingerprint keeps an unrecorded source from merging; it is the check for this case.
- **Issues:** `--open-issue` (needs `GITHUB_TOKEN`) opens one issue naming the facts and quoting
  the old and new text. If one is already open, the run adds one comment to it naming only the
  changed or gone sources that the issue and its comments do not name yet (nothing if all are named).
  A source counts as named only if its exact URL appears whole in the issue or in a comment written
  after the date its fingerprint was last recorded; comments are read page by page.
- **Recording:** `--accept URL` (repeatable, after a person re-verified its facts) rewrites only
  that URL, and that URL is not reported or filed in the same run. Only `--record` stores new sources and prunes ones no fact cites any more.
- **Outcomes:** unchanged (silent), changed, gone (HTTP 404 or 410 only), unreachable (blocked,
  timeout, DNS or connection error, server error: "can't check", no alarm), new (no stored
  fingerprint yet), not watched.
- **Can't, or watch out:**
  - **It sees that text changed, not whether it matters.** A person decides.
  - **It misses changes reported elsewhere** (news before the source page itself changes).
  - **PDFs and other files are fingerprinted by their bytes, which is coarser:** a re-saved PDF
    alarms although its words are the same.
  - **Search-index lag:** the GitHub search can lag a few seconds, so two runs started within
    seconds of each other could each open an issue. The watch runs by hand or monthly, one run at
    a time; if a duplicate happens, a person closes it.
  - **The baseline is from the day it was recorded** (the `recorded` date in the file), not the
    day each fact was checked; a source that changed in between shows as "unchanged".

## Data releases (the `Refresh data` workflow)
`airport-agent refresh` can also run on GitHub's machine: the `Refresh data` workflow
(`.github/workflows/refresh.yml`, weekly on Mondays or started by hand) builds a snapshot, checks
it like any snapshot (manifest present, names its version, every listed file there), compares it
with the previous data release (each source's as-of date and the national top 10) and publishes
it as a GitHub release `data-YYYY-MM-DD` (`-2`, `-3` for a second run that day): the snapshot
folder as one `.tar.gz`, its `manifest.json`, and the comparison as the release text. Running
servers download the newest one (`data/releases.py`), refusing an archive that is not one complete
snapshot (every summary listed and loading with the server's own loader), has a path or link
outside it, or is over 2,000 files or 200 MB unpacked. OpenSky credentials are optional repository
secrets (`OPENSKY_CLIENT_ID`, `OPENSKY_CLIENT_SECRET`); without them the release uses the committed
OpenSky sample and its manifest says so. Rolling back bad data starts with deleting its release.
Where a restart throws installed files away (Fly: the data store is inside the machine, with no
volume), servers then load the previous release when they next start. Where installed files are
kept (a data store on a disk or volume), also delete the installed `latest-…` folder from the
data store; `DATA_RELEASES=off` stops a server from downloading releases at all.
