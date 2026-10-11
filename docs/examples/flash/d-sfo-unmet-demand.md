# d-sfo-unmet-demand

Model: `gemini-3.8-flash`. Run on 2026-10-11.

## Question 1

> Is there unmet demand at SFO, and why?

### Tool calls (2)

1. `demand_pressure` {"code": "SFO"}

   - SFO: top quartile nationally: delay; bottom quartile: cancellations, growth.
   - delay: percentile 100.0, value 9.84
   - cancellations: percentile 24.6, value 0.0107
   - fare premium: percentile 44.9, value 1.005
   - growth: percentile 20.2, value -8.8

   <details><summary>Full result</summary>

   ```json
   {
     "code": "SFO",
     "name": "San Francisco International Airport",
     "ranked": true,
     "ranked_nationally": 138,
     "signals": {
       "delay": {
         "group": "strain",
         "percentile": 100.0,
         "value": 9.84,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "145831 landed of 147716 scheduled in 12 months"
       },
       "cancellations": {
         "group": "strain",
         "percentile": 24.6,
         "value": 0.0107,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 1.1,
         "note": "1579 cancelled, 306 diverted"
       },
       "fare premium": {
         "group": "strain",
         "percentile": 44.9,
         "value": 1.005,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth": {
         "group": "growth",
         "percentile": 20.2,
         "value": -8.8,
         "unit": "% change in passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1 vs 2019 Q1",
         "note": "58683.3 per day in 2019 Q1"
       }
     },
     "friction": {
       "name": "Runway spacing and Bay fill",
       "points": 20,
       "tier": "major",
       "description": "Runways 28L and 28R are 750 ft apart, so in instrument conditions (low cloud or fog) they can't take side-by-side arrivals, and the hourly rate falls from 104-107 to 71-78 operations. Widening the gap needs Bay fill: a BCDC permit, and since 2001 (Proposition D) a city vote for any project with more than 100 acres of fill. The 1999 runway plan considered up to about 1,500 acres of fill; the runways were never moved.",
       "sources": [
         "https://www.faa.gov/documentLibrary/media/Order/2017-07-10_JO_7110.308B_Simultaneous_Dependent_Approaches_to_Closely_Parallel_Runways.pdf",
         "https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/SFO-Airport-Capacity-Profile-2019.pdf",
         "https://www.govinfo.gov/content/pkg/FR-1999-07-01/html/99-16756.htm",
         "https://sfbos.org/introduction-4"
       ],
       "checked": "2026-10-11",
       "review_by": "2027-10-11"
     },
     "confidence": "High",
     "summary": "SFO: top quartile nationally: delay; bottom quartile: cancellations, growth.",
     "percentile_note": "percentile 100 = highest of all airports ranked nationally; higher means more strain or more growth"
   }
   ```

   </details>

2. `airport_profile` {"code": "SFO"}

   - SFO San Francisco International Airport: ranked: lower 48 and in DOT Table 1a for 2026 Q1
   - measured: nas_delay_per_landed_flight, cancellation_rate, fare_premium, growth_vs_2019, passengers_per_day, market_count, largest_carrier, largest_carrier_share, enplanements
   - verified facts (notes): [6, 7]

   <details><summary>Full result</summary>

   ```json
   {
     "code": "SFO",
     "icao": "KSFO",
     "name": "San Francisco International Airport",
     "state": "CA",
     "ranked": true,
     "scope": "ranked: lower 48 and in DOT Table 1a for 2026 Q1",
     "metrics": {
       "nas_delay_per_landed_flight": {
         "value": 9.84,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "145831 landed of 147716 scheduled in 12 months"
       },
       "cancellation_rate": {
         "value": 0.0107,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 1.1,
         "note": "1579 cancelled, 306 diverted"
       },
       "fare_premium": {
         "value": 1.005,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth_vs_2019": {
         "value": -8.8,
         "unit": "% change in passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1 vs 2019 Q1",
         "note": "58683.3 per day in 2019 Q1"
       },
       "passengers_per_day": {
         "value": 53518.7,
         "unit": "passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "sum over the airport's listed markets; domestic only"
       },
       "market_count": {
         "value": 61,
         "unit": "markets",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1"
       },
       "largest_carrier": {
         "value": "UA",
         "unit": "carrier code",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1"
       },
       "largest_carrier_share": {
         "value": 0.394,
         "unit": "share of passengers",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "value_pct": 39.4,
         "note": "lower bound: counts only markets this carrier leads; shown, not scored"
       },
       "enplanements": {
         "value": 24176902,
         "unit": "passengers boarded per year",
         "source": "BTS passenger boardings (top 50 airports) (https://data.bts.gov/resource/2ydv-qfge.json)",
         "as_of": "2023",
         "note": "rank 13 of the top 50"
       }
     },
     "missing": {
       "long_haul_share": "computed only for Anchorage (OpenSky)"
     },
     "verified_facts": [
       {
         "note": 6,
         "fact": "SFO runways 28L/28R are 750 ft apart (centreline to centreline). In good weather two planes can land side by side; in instrument conditions (low cloud or fog) they can't, and arrivals are flown as staggered pairs instead. FAA's capacity profile shows the airport's hourly rate falling from 104–107 operations (visual, side by side) to 71–78 (instrument): a drop of roughly a quarter to a third, not a halving",
         "sources": [
           "https://www.faa.gov/documentLibrary/media/Order/2017-07-10_JO_7110.308B_Simultaneous_Dependent_Approaches_to_Closely_Parallel_Runways.pdf",
           "https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/SFO-Airport-Capacity-Profile-2019.pdf"
         ],
         "checked": "2026-10-11",
         "review_by": "2027-10-11"
       },
       {
         "note": 7,
         "fact": "SFO can't widen the runway gap without Bay fill. BCDC issues Bay fill permits under the McAteer-Petris Act. A 1999 runway reconfiguration plan considered up to about 1,500 acres of fill; in 2001 San Francisco voters passed Proposition D, requiring a public vote for any city project with more than 100 acres of Bay fill, which covered every runway option under study. The runways were never moved.",
         "sources": [
           "https://www.govinfo.gov/content/pkg/FR-1999-07-01/html/99-16756.htm",
           "https://sfbos.org/introduction-4",
           "https://ceqanet.lci.ca.gov/1999072002"
         ],
         "checked": "2026-10-11",
         "review_by": "2027-10-11"
       }
     ]
   }
   ```

   </details>

### Answer

At San Francisco International Airport (SFO), signs of unmet demand are mixed: while the airport suffers from severe operational strain in delays (highest nationally), actual passenger traffic remains below pre-pandemic levels, and cancellation and fare premium strain remain moderate to low.

The severe operational strain at SFO is heavily driven by physical airfield constraints:
- **Runway spacing:** Runways 28L and 28R are 750 ft apart (centreline to centreline). In visual conditions, two planes can land side by side, but in instrument conditions (low cloud or fog), they cannot and arrivals must be flown as staggered pairs. According to the FAA's capacity profile, the hourly rate drops from 104–107 operations to 71–78 operations (Note 6, [FAA Order JO 7110.308B](https://www.faa.gov/documentLibrary/media/Order/2017-07-10_JO_7110.308B_Simultaneous_Dependent_Approaches_to_Closely_Parallel_Runways.pdf) and [FAA SFO Capacity Profile](https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/SFO-Airport-Capacity-Profile-2019.pdf), checked 2026-10-11).
- **Physical expansion barriers:** SFO cannot widen this runway gap without Bay fill. Any permit requires BCDC approval under the McAteer-Petris Act. Following the 1999 runway reconfiguration plan (which considered up to about 1,500 acres of fill), San Francisco voters passed Proposition D in 2001, requiring a public vote for any city project with more than 100 acres of Bay fill, covering every option studied; the runways were never moved (Note 7, [Federal Register Notice](https://www.govinfo.gov/content/pkg/FR-1999-07-01/html/99-16756.htm), [SF Board of Supervisors](https://sfbos.org/introduction-4), and [CEQAnet](https://ceqanet.lci.ca.gov/1999072002), checked 2026-10-11).

### Demand and Strain Numbers

| Signal | Group | Measured Value | National Percentile | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Delay** | Strain | 9.84 NAS delay min / landed flight | 100.0 | 145,831 landed of 147,716 scheduled |
| **Fare premium** | Strain | 1.005 ratio | 44.9 | 1.0 = normal fares for distances |
| **Cancellations** | Strain | 0.0107 (1.1%) | 24.6 | 1,579 cancelled, 306 diverted |
| **Growth** | Growth | -8.8% | 20.2 | 58,683.3 passengers/day in 2019 Q1 |

- **Friction Penalty:** Applied (20 points, tier: major) due to runway spacing and Bay fill constraints (checked 2026-10-11).
- **Confidence:** High.
- **National Rank:** Ranked 138 nationally for unmet demand pressure.

---

### Assumptions and data
- **Thresholds & Definitions:** 
  - Percentile 100 = highest of all airports ranked nationally; higher means more strain or more growth.
  - Delay measured as NAS delay minutes per landed flight.
  - Cancellations measured as cancelled ÷ (scheduled − diverted).
  - Fare premium measured as ratio to national fare per mile.
  - Growth measured as % change in passengers per day (domestic listed markets).
- **Data Sources:**
  - BTS On-Time Performance (Reporting Carrier) ([BTS](https://transtats.bts.gov/PREZIP/)): as of Aug 2025 to Jul 2026.
  - DOT Consumer Airfare Report, Table 1a ([DOT Data Hub](https://datahub.transportation.gov/resource/tfrh-tu9e.json)): as of 2026 Q1 and 2026 Q1 vs 2019 Q1.
  - Verified facts and friction details: FAA capacity profile and orders, SF Board of Supervisors, CEQAnet, Federal Register (checked 2026-10-11).

### Run

- Seconds: 10.9
- Tokens: 3,328 in / 1,069 out / 0 thinking
- Cost: $0.0065
- Number check: all numbers found in tool results
