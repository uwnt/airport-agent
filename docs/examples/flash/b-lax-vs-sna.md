# b-lax-vs-sna

Model: `gemini-3.8-flash`. Run on 2026-10-11.

## Question 1

> How do LAX and SNA compare on congestion?

### Tool calls (5)

1. `compare_airports` {"codes": ["LAX", "SNA"], "preset": "congestion-focused"}

   - preset congestion-focused, weights {'delay': 35.0, 'cancellations': 17.5, 'fare premium': 17.5, 'growth': 30.0}, 138 ranked nationally
   - #1 LAX score 25.7 (national #126, High confidence)
   - #2 SNA score 1.0 (national #138, High confidence, friction -30)

   <details><summary>Full result</summary>

   ```json
   {
     "preset": "congestion-focused",
     "weights_pct": {
       "delay": 35.0,
       "cancellations": 17.5,
       "fare premium": 17.5,
       "growth": 30.0
     },
     "ranked_nationally": 138,
     "region": null,
     "rows": [
       {
         "code": "LAX",
         "name": "Los Angeles International Airport",
         "state": "CA",
         "rank": 1,
         "national_rank": 126,
         "score": 25.7,
         "score_before_friction": 25.7,
         "signals": {
           "delay": {
             "points": 11.4,
             "percentile": 32.6,
             "weight_pct": 35.0,
             "value": 2.09,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "188023 landed of 190125 scheduled in 12 months"
           },
           "cancellations": {
             "points": 3.8,
             "percentile": 21.7,
             "weight_pct": 17.5,
             "value": 0.0099,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 1.0,
             "note": "1877 cancelled, 225 diverted"
           },
           "fare premium": {
             "points": 6.7,
             "percentile": 38.4,
             "weight_pct": 17.5,
             "value": 0.972,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 3.7,
             "percentile": 12.4,
             "weight_pct": 30.0,
             "value": -21.1,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "90607.3 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       },
       {
         "code": "SNA",
         "name": "John Wayne Orange County International Airport",
         "state": "CA",
         "rank": 2,
         "national_rank": 138,
         "score": 1.0,
         "score_before_friction": 31.0,
         "signals": {
           "delay": {
             "points": 8.1,
             "percentile": 23.2,
             "weight_pct": 35.0,
             "value": 1.75,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "44681 landed of 45231 scheduled in 12 months"
           },
           "cancellations": {
             "points": 3.3,
             "percentile": 18.8,
             "weight_pct": 17.5,
             "value": 0.0091,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 0.9,
             "note": "409 cancelled, 141 diverted"
           },
           "fare premium": {
             "points": 10.7,
             "percentile": 61.2,
             "weight_pct": 17.5,
             "value": 1.052,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 8.8,
             "percentile": 29.5,
             "weight_pct": 30.0,
             "value": -0.7,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "21086.2 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "Passenger cap",
           "points": 30,
           "tier": "hard_cap",
           "description": "Annual passenger cap under the 1985 settlement agreement as amended: 11.8 million through 2025; 12.2 million for 2026 to 2030, or 12.5 million only if 11.21 million were served in 2021 to 2025 and certain mitigation measures are met. The agreement runs to 31 Dec 2030.",
           "sources": [
             "https://www.ocair.com/about/administration/settlement-agreement/key-provisions-settlement-agreement",
             "https://www.ocair.com/about/administration/settlement-agreement/settlement-agreement-faqs"
           ],
           "checked": "2026-10-11",
           "review_by": "2030-12-31"
         },
         "confidence": "High",
         "friction_not_counted": [
           "Curfew (minor, 10 points; only the largest penalty counts)"
         ]
       }
     ],
     "not_ranked": [],
     "method": "score = sum of each signal's percentile (0-100, across all airports ranked nationally) times its weight, minus the largest friction penalty, never below 0; settings from config/scoring.yaml"
   }
   ```

   </details>

2. `demand_pressure` {"code": "LAX"}

   - LAX: top quartile nationally: none; bottom quartile: cancellations, growth.
   - delay: percentile 32.6, value 2.09
   - cancellations: percentile 21.7, value 0.0099
   - fare premium: percentile 38.4, value 0.972
   - growth: percentile 12.4, value -21.1

   <details><summary>Full result</summary>

   ```json
   {
     "code": "LAX",
     "name": "Los Angeles International Airport",
     "ranked": true,
     "ranked_nationally": 138,
     "signals": {
       "delay": {
         "group": "strain",
         "percentile": 32.6,
         "value": 2.09,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "188023 landed of 190125 scheduled in 12 months"
       },
       "cancellations": {
         "group": "strain",
         "percentile": 21.7,
         "value": 0.0099,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 1.0,
         "note": "1877 cancelled, 225 diverted"
       },
       "fare premium": {
         "group": "strain",
         "percentile": 38.4,
         "value": 0.972,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth": {
         "group": "growth",
         "percentile": 12.4,
         "value": -21.1,
         "unit": "% change in passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1 vs 2019 Q1",
         "note": "90607.3 per day in 2019 Q1"
       }
     },
     "friction": {
       "name": "none on file",
       "points": 0
     },
     "confidence": "High",
     "summary": "LAX: top quartile nationally: none; bottom quartile: cancellations, growth.",
     "percentile_note": "percentile 100 = highest of all airports ranked nationally; higher means more strain or more growth"
   }
   ```

   </details>

3. `demand_pressure` {"code": "SNA"}

   - SNA: top quartile nationally: none; bottom quartile: delay, cancellations.
   - delay: percentile 23.2, value 1.75
   - cancellations: percentile 18.8, value 0.0091
   - fare premium: percentile 61.2, value 1.052
   - growth: percentile 29.5, value -0.7

   <details><summary>Full result</summary>

   ```json
   {
     "code": "SNA",
     "name": "John Wayne Orange County International Airport",
     "ranked": true,
     "ranked_nationally": 138,
     "signals": {
       "delay": {
         "group": "strain",
         "percentile": 23.2,
         "value": 1.75,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "44681 landed of 45231 scheduled in 12 months"
       },
       "cancellations": {
         "group": "strain",
         "percentile": 18.8,
         "value": 0.0091,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 0.9,
         "note": "409 cancelled, 141 diverted"
       },
       "fare premium": {
         "group": "strain",
         "percentile": 61.2,
         "value": 1.052,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth": {
         "group": "growth",
         "percentile": 29.5,
         "value": -0.7,
         "unit": "% change in passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1 vs 2019 Q1",
         "note": "21086.2 per day in 2019 Q1"
       }
     },
     "friction": {
       "name": "Passenger cap",
       "points": 30,
       "tier": "hard_cap",
       "description": "Annual passenger cap under the 1985 settlement agreement as amended: 11.8 million through 2025; 12.2 million for 2026 to 2030, or 12.5 million only if 11.21 million were served in 2021 to 2025 and certain mitigation measures are met. The agreement runs to 31 Dec 2030.",
       "sources": [
         "https://www.ocair.com/about/administration/settlement-agreement/key-provisions-settlement-agreement",
         "https://www.ocair.com/about/administration/settlement-agreement/settlement-agreement-faqs"
       ],
       "checked": "2026-10-11",
       "review_by": "2030-12-31"
     },
     "confidence": "High",
     "summary": "SNA: top quartile nationally: none; bottom quartile: delay, cancellations.",
     "percentile_note": "percentile 100 = highest of all airports ranked nationally; higher means more strain or more growth"
   }
   ```

   </details>

4. `airport_profile` {"code": "LAX"}

   - LAX Los Angeles International Airport: ranked: lower 48 and in DOT Table 1a for 2026 Q1
   - measured: nas_delay_per_landed_flight, cancellation_rate, fare_premium, growth_vs_2019, passengers_per_day, market_count, largest_carrier, largest_carrier_share, enplanements
   - verified facts (notes): [5]

   <details><summary>Full result</summary>

   ```json
   {
     "code": "LAX",
     "icao": "KLAX",
     "name": "Los Angeles International Airport",
     "state": "CA",
     "ranked": true,
     "scope": "ranked: lower 48 and in DOT Table 1a for 2026 Q1",
     "metrics": {
       "nas_delay_per_landed_flight": {
         "value": 2.09,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "188023 landed of 190125 scheduled in 12 months"
       },
       "cancellation_rate": {
         "value": 0.0099,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 1.0,
         "note": "1877 cancelled, 225 diverted"
       },
       "fare_premium": {
         "value": 0.972,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth_vs_2019": {
         "value": -21.1,
         "unit": "% change in passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1 vs 2019 Q1",
         "note": "90607.3 per day in 2019 Q1"
       },
       "passengers_per_day": {
         "value": 71499.5,
         "unit": "passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "sum over the airport's listed markets; domestic only"
       },
       "market_count": {
         "value": 83,
         "unit": "markets",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1"
       },
       "largest_carrier": {
         "value": "DL",
         "unit": "carrier code",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1"
       },
       "largest_carrier_share": {
         "value": 0.142,
         "unit": "share of passengers",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "value_pct": 14.2,
         "note": "lower bound: counts only markets this carrier leads; shown, not scored"
       },
       "enplanements": {
         "value": 36615633,
         "unit": "passengers boarded per year",
         "source": "BTS passenger boardings (top 50 airports) (https://data.bts.gov/resource/2ydv-qfge.json)",
         "as_of": "2023",
         "note": "rank 4 of the top 50"
       }
     },
     "missing": {
       "long_haul_share": "computed only for Anchorage (OpenSky)"
     },
     "verified_facts": [
       {
         "note": 5,
         "fact": "About 22% of air passengers in the Southern California region come from Orange County, but SNA served only about 11% of them, so many Orange County travellers use LAX or other airports.",
         "sources": [
           "https://sustain.scag.ca.gov/sites/default/files/2024-05/23-2987-tr-aviation-airport-ground-access-final-040424.pdf"
         ],
         "checked": "2026-10-11",
         "review_by": "2027-10-11"
       }
     ]
   }
   ```

   </details>

5. `airport_profile` {"code": "SNA"}

   - SNA John Wayne Orange County International Airport: ranked: lower 48 and in DOT Table 1a for 2026 Q1
   - measured: nas_delay_per_landed_flight, cancellation_rate, fare_premium, growth_vs_2019, passengers_per_day, market_count, largest_carrier, largest_carrier_share, enplanements
   - verified facts (notes): [2, 3, 5]

   <details><summary>Full result</summary>

   ```json
   {
     "code": "SNA",
     "icao": "KSNA",
     "name": "John Wayne Orange County International Airport",
     "state": "CA",
     "ranked": true,
     "scope": "ranked: lower 48 and in DOT Table 1a for 2026 Q1",
     "metrics": {
       "nas_delay_per_landed_flight": {
         "value": 1.75,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "44681 landed of 45231 scheduled in 12 months"
       },
       "cancellation_rate": {
         "value": 0.0091,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 0.9,
         "note": "409 cancelled, 141 diverted"
       },
       "fare_premium": {
         "value": 1.052,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth_vs_2019": {
         "value": -0.7,
         "unit": "% change in passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1 vs 2019 Q1",
         "note": "21086.2 per day in 2019 Q1"
       },
       "passengers_per_day": {
         "value": 20946.2,
         "unit": "passengers per day",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "sum over the airport's listed markets; domestic only"
       },
       "market_count": {
         "value": 86,
         "unit": "markets",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1"
       },
       "largest_carrier": {
         "value": "WN",
         "unit": "carrier code",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1"
       },
       "largest_carrier_share": {
         "value": 0.237,
         "unit": "share of passengers",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "value_pct": 23.7,
         "note": "lower bound: counts only markets this carrier leads; shown, not scored"
       },
       "enplanements": {
         "value": 5658796,
         "unit": "passengers boarded per year",
         "source": "BTS passenger boardings (top 50 airports) (https://data.bts.gov/resource/2ydv-qfge.json)",
         "as_of": "2023",
         "note": "rank 41 of the top 50"
       }
     },
     "missing": {
       "long_haul_share": "computed only for Anchorage (OpenSky)"
     },
     "verified_facts": [
       {
         "note": 2,
         "fact": "SNA passenger cap under the 1985 settlement as amended: 11.8M annual passengers through 2025; for 2026–2030 the cap is 12.2M, or 12.5M only if 11.21M was served in 2021–2025 and certain mitigation measures are met. The agreement runs to 31 Dec 2030 (the curfew obligation runs to 2035)",
         "sources": [
           "https://www.ocair.com/about/administration/settlement-agreement/key-provisions-settlement-agreement",
           "https://www.ocair.com/about/administration/settlement-agreement/settlement-agreement-faqs"
         ],
         "checked": "2026-10-11",
         "review_by": "2030-12-31"
       },
       {
         "note": 3,
         "fact": "SNA curfew: no commercial departures from 10 pm to 7 am (8 am on Sundays) and no commercial arrivals from 11 pm to 7 am (8 am on Sundays); the Airport Director may allow exceptions for emergency, mechanical, air traffic control or weather delays",
         "sources": [
           "https://www.ocair.com/about/administration/access-noise/reports-resources/"
         ],
         "checked": "2026-10-11",
         "review_by": "2030-12-31"
       },
       {
         "note": 5,
         "fact": "About 22% of air passengers in the Southern California region come from Orange County, but SNA served only about 11% of them, so many Orange County travellers use LAX or other airports.",
         "sources": [
           "https://sustain.scag.ca.gov/sites/default/files/2024-05/23-2987-tr-aviation-airport-ground-access-final-040424.pdf"
         ],
         "checked": "2026-10-11",
         "review_by": "2027-10-11"
       }
     ]
   }
   ```

   </details>

### Answer

Under the congestion-focused preset, **LAX outscores SNA (25.7 vs 1.0)** primarily because SNA incurs a **30-point passenger cap friction penalty**, which reduces its score from 31.0 to 1.0. 

Looking strictly at operational congestion strain:
- **Delay:** LAX experiences slightly more delay (2.09 NAS delay minutes per landed flight, 32.6th percentile) than SNA (1.75 minutes, 23.2nd percentile).
- **Cancellations:** LAX has a slightly higher cancellation rate (1.0%, 21.7th percentile) than SNA (0.9%, 18.8th percentile).
- **Fare Premium:** SNA shows higher pricing pressure with a fare premium ratio of 1.052 (61.2th percentile), whereas LAX is below the national average at 0.972 (38.4th percentile).
- **Growth:** Both airports remain below 2019 passenger levels, but SNA (-0.7%, 29.5th percentile) has recovered significantly closer to 2019 levels than LAX (-21.1%, 12.4th percentile).

---

### Congestion & Demand Signals Comparison

| Metric / Signal | LAX Value (Percentile) | SNA Value (Percentile) | Congestion Weight |
| :--- | :--- | :--- | :--- |
| **Delay** (NAS delay min/landed flight) | 2.09 (32.6%) | 1.75 (23.2%) | 35.0% |
| **Cancellations** (rate) | 1.0% / 0.0099 (21.7%) | 0.9% / 0.0091 (18.8%) | 17.5% |
| **Fare Premium** (fare/mile ratio) | 0.972 (38.4%) | 1.052 (61.2%) | 17.5% |
| **Growth vs 2019** (% pax/day change) | -21.1% (12.4%) | -0.7% (29.5%) | 30.0% |
| **Score before friction** | 25.7 | 31.0 | — |
| **Friction penalty** | 0 (none on file) | -30.0 (Passenger cap) | — |
| **Final Congestion Score** | **25.7** (National Rank: 126) | **1.0** (National Rank: 138) | — |
| **Confidence** | High | High | — |

---

### Friction & Verified Facts

- **SNA Passenger Cap Penalty:** SNA receives a 30-point friction deduction for a hard passenger cap. Under the 1985 settlement agreement as amended, the annual passenger cap is 11.8 million through 2025; 12.2 million for 2026 to 2030, or 12.5 million only if 11.21 million were served in 2021 to 2025 and certain mitigation measures are met (agreement runs to 31 Dec 2030; checked 2026-10-11, Note 2 [Source](https://www.ocair.com/about/administration/settlement-agreement/key-provisions-settlement-agreement)). SNA also has an uncounted curfew penalty (10 points; only the largest penalty counts; Note 3 [Source](https://www.ocair.com/about/administration/access-noise/reports-resources/), checked 2026-10-11).
- **Regional Traffic Leakage:** About 22% of air passengers in the Southern California region come from Orange County, but SNA served only about 11% of them, so many Orange County travellers use LAX or other airports (checked 2026-10-11, Note 5 [Source](https://sustain.scag.ca.gov/sites/default/files/2024-05/23-2987-tr-aviation-airport-ground-access-final-040424.pdf)).
- **LAX:** No friction penalties on file.

---

### Assumptions and data

- **Scoring Preset:** `congestion-focused`
  - Weights: delay 35.0%, growth 30.0%, cancellations 17.5%, fare premium 17.5%.
  - Scoring method: Score = sum of each signal's national percentile (0–100) multiplied by its weight, minus the largest friction penalty (never below 0).
- **Data Sources and Dates:**
  - **Delay & Cancellations:** BTS On-Time Performance (Reporting Carrier) ([link](https://transtats.bts.gov/PREZIP/)), as of **Aug 2025 to Jul 2026**.
  - **Fare Premium:** DOT Consumer Airfare Report, Table 1a ([link](https://datahub.transportation.gov/resource/tfrh-tu9e.json)), as of **2026 Q1** (1.0 = normal fares for those distances).
  - **Growth:** DOT Consumer Airfare Report, Table 1a ([link](https://datahub.transportation.gov/resource/tfrh-tu9e.json)), as of **2026 Q1 vs 2019 Q1**.

### Run

- Seconds: 15.9
- Tokens: 3,416 in / 1,368 out / 0 thinking
- Cost: $0.0077
- Number check: all numbers found in tool results
