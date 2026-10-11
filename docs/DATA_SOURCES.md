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
  trimmed to the fields we use, and private tail numbers are masked as `PRIVATE`.
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
