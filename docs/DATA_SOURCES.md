# Data sources: what each one can and can't answer

Checked by hand on 2026-10-11 (Step 1). Each source has a spike script in `scripts/spike/` and a
small sample in `data/samples/`, which later serves as an offline test fixture.

The four example questions: **Q1** New England expansion candidates · **Q2** LAX vs SNA congestion ·
**Q3** long-haul share out of Anchorage · **Q4** unmet demand at SFO, and why.

## DOT Consumer Airfare Report, Table 1a
- **Gives:** for each airport pair and quarter (1993 to 2026 Q1): passengers per day, average fare,
  distance, the largest carrier and its share.
- **Helps with:** Q1 (volume, growth, fare premium), Q2 and Q4 (volume, growth).
- **Can't:**
  - **No Alaska:** Anchorage has no rows, so Q3 needs OpenSky.
  - **Domestic only:** international passengers are not in it.
  - **Busiest markets only:** small airports are undercounted. BTV shows ~250 passengers a day,
    far below its real traffic. Treat small-airport totals as a lower bound.
- **Trap found:** compare the same quarter across years. Q4 2019 vs Q1 2026 made Boston look
  24% down; Q1 vs Q1 shows 10% down.

## BTS enplanements (top 50 airports)
- **Gives:** boarded passengers per airport per year, 2003–2023, with coordinates.
- **Helps with:** a size check for large airports (BOS, LAX, SFO, ANC).
- **Can't:**
  - **Top 50 only:** New England airports other than BOS are missing.
  - **Stops at 2023.**

## BTS On-Time Performance
- **Gives:** every domestic flight by a reporting airline, with delay minutes split by cause. NAS
  delay is the part caused by the airport and airspace system; weather is counted separately.
- **Helps with:** congestion for Q2 and Q4. This is the only *measured* public congestion signal.
- **Sample (July 2026):** NAS delay minutes per arriving flight:

  | SFO | EWR | BOS | ORD | LAX | SNA | ANC |
  |---|---|---|---|---|---|---|
  | 15.0 | 11.8 | 9.1 | 7.7 | 2.2 | 2.2 | 1.9 |

- **Can't:**
  - **Doesn't separate LAX from SNA:** both show 2.2, so Q2 needs a second congestion measure.
  - **One summer month is not a year.**
  - **Large raw files:** each month is a ~32 MB download; we keep only the per-airport summary.
  - **About 2–3 months behind.**

## FAA NAS Status
- **Gives:** delay programs, ground stops and closures, right now.
- **Helps with:** a "current conditions" line in an answer.
- **Can't:** give any history. It can't be used for scoring.

## OurAirports
- **Gives:** every airport's codes, type, region and coordinates. 679 US airports have scheduled
  service and an IATA code.
- **Helps with:** every question. It is the code lookup between IATA (DOT uses `SFO`) and ICAO
  (OpenSky uses `KSFO`), and the coordinates give distances for Q3.
- **Watch:** Alaska ICAO codes start with P (Anchorage is `PANC`), so "add a K" is wrong.

## OpenSky Network (free account)
- **Gives:** actual departures and arrivals per airport from transponder data, with an *estimated*
  destination.
- **Helps with:** Q3 (where Anchorage flights go), flights per hour for Q2.
- **Sample:** 552 departures from Anchorage in two days.
- **Can't, or watch out:**
  - **Cargo and private flights are mixed in.** Prefixes like GTI, FDX, CKS and UPS are cargo;
    callsigns starting with `N` are private aircraft. Filter by a fixed passenger-airline list.
  - **Destination unknown for ~14%** of flights.
  - **Terms restrict commercial use** (see decision D5).
  - **No deep history on a free account.**
