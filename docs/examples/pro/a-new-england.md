# a-new-england

Model: `gemini-3.1-pro-preview`. Run on 2026-10-11.

## Question 1

> Which New England airports are the best terminal-expansion candidates?

### Tool calls (1)

1. `rank_airports` {"region": "New England", "preset": "balanced"}

   - preset balanced, weights {'delay': 25.0, 'cancellations': 12.5, 'fare premium': 12.5, 'growth': 50.0}, 138 ranked nationally
   - #1 BOS score 48.2 (national #77, High confidence)
   - #2 BGR score 46.0 (national #85, Low confidence)
   - #3 BTV score 36.3 (national #100, Low confidence)
   - #4 PVD score 34.7 (national #106, High confidence)
   - #5 BDL score 32.0 (national #113, High confidence)
   - #6 PWM score 29.5 (national #116, Low confidence)
   - #7 MHT score 17.8 (national #130, High confidence)
   - not ranked: HVN (no measured delay data)

   <details><summary>Full result</summary>

   ```json
   {
     "preset": "balanced",
     "weights_pct": {
       "delay": 25.0,
       "cancellations": 12.5,
       "fare premium": 12.5,
       "growth": 50.0
     },
     "ranked_nationally": 138,
     "region": "New England",
     "rows": [
       {
         "code": "BOS",
         "name": "Boston Logan International Airport",
         "state": "MA",
         "rank": 1,
         "national_rank": 77,
         "score": 48.2,
         "score_before_friction": 48.2,
         "signals": {
           "delay": {
             "points": 24.1,
             "percentile": 96.4,
             "weight_pct": 25.0,
             "value": 6.88,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "139256 landed of 143441 scheduled in 12 months"
           },
           "cancellations": {
             "points": 10.8,
             "percentile": 86.2,
             "weight_pct": 12.5,
             "value": 0.0279,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 2.8,
             "note": "3993 cancelled, 192 diverted"
           },
           "fare premium": {
             "points": 4.4,
             "percentile": 35.5,
             "weight_pct": 12.5,
             "value": 0.959,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 8.9,
             "percentile": 17.8,
             "weight_pct": 50.0,
             "value": -10.2,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "57203.7 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       },
       {
         "code": "BGR",
         "name": "Bangor International Airport",
         "state": "ME",
         "rank": 2,
         "national_rank": 85,
         "score": 46.0,
         "score_before_friction": 46.0,
         "signals": {
           "delay": {
             "points": 21.7,
             "percentile": 43.5,
             "weight_pct": 50.0,
             "value": 2.31,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "3836 landed of 3984 scheduled in 12 months"
           },
           "cancellations": {
             "points": 23.9,
             "percentile": 95.7,
             "weight_pct": 25.0,
             "value": 0.034,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 3.4,
             "note": "135 cancelled, 13 diverted"
           },
           "fare premium": {
             "points": 0.4,
             "percentile": 1.4,
             "weight_pct": 25.0,
             "value": 0.437,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "missing": "no DOT Table 1a rows for 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "Low",
         "confidence_reasons": [
           "growth missing: no DOT Table 1a rows for 2019 Q1",
           "only 2 market(s) in DOT Table 1a (fewer than 10)"
         ]
       },
       {
         "code": "BTV",
         "name": "Patrick Leahy Burlington International Airport",
         "state": "VT",
         "rank": 3,
         "national_rank": 100,
         "score": 36.3,
         "score_before_friction": 36.3,
         "signals": {
           "delay": {
             "points": 19.0,
             "percentile": 76.1,
             "weight_pct": 25.0,
             "value": 3.02,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "5884 landed of 6084 scheduled in 12 months"
           },
           "cancellations": {
             "points": 11.1,
             "percentile": 88.4,
             "weight_pct": 12.5,
             "value": 0.0287,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 2.9,
             "note": "174 cancelled, 26 diverted"
           },
           "fare premium": {
             "points": 5.1,
             "percentile": 40.6,
             "weight_pct": 12.5,
             "value": 0.984,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 1.2,
             "percentile": 2.3,
             "weight_pct": 50.0,
             "value": -56.3,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "578.7 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "Low",
         "confidence_reasons": [
           "only 3 market(s) in DOT Table 1a (fewer than 10)"
         ]
       },
       {
         "code": "PVD",
         "name": "Rhode Island T. F. Green International Airport",
         "state": "RI",
         "rank": 4,
         "national_rank": 106,
         "score": 34.7,
         "score_before_friction": 34.7,
         "signals": {
           "delay": {
             "points": 8.9,
             "percentile": 35.5,
             "weight_pct": 25.0,
             "value": 2.13,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "15152 landed of 15593 scheduled in 12 months"
           },
           "cancellations": {
             "points": 10.2,
             "percentile": 81.9,
             "weight_pct": 12.5,
             "value": 0.0267,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 2.7,
             "note": "416 cancelled, 25 diverted"
           },
           "fare premium": {
             "points": 2.8,
             "percentile": 22.5,
             "weight_pct": 12.5,
             "value": 0.869,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 12.8,
             "percentile": 25.6,
             "weight_pct": 50.0,
             "value": -2.9,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "6817.8 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       },
       {
         "code": "BDL",
         "name": "Bradley International Airport",
         "state": "CT",
         "rank": 5,
         "national_rank": 113,
         "score": 32.0,
         "score_before_friction": 32.0,
         "signals": {
           "delay": {
             "points": 12.9,
             "percentile": 51.4,
             "weight_pct": 25.0,
             "value": 2.43,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "21777 landed of 22344 scheduled in 12 months"
           },
           "cancellations": {
             "points": 9.1,
             "percentile": 72.5,
             "weight_pct": 12.5,
             "value": 0.0235,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 2.4,
             "note": "524 cancelled, 43 diverted"
           },
           "fare premium": {
             "points": 5.4,
             "percentile": 43.5,
             "weight_pct": 12.5,
             "value": 0.996,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 4.7,
             "percentile": 9.3,
             "weight_pct": 50.0,
             "value": -22.8,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "4570.3 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       },
       {
         "code": "PWM",
         "name": "Portland International Jetport",
         "state": "ME",
         "rank": 6,
         "national_rank": 116,
         "score": 29.5,
         "score_before_friction": 29.5,
         "signals": {
           "delay": {
             "points": 8.0,
             "percentile": 31.9,
             "weight_pct": 25.0,
             "value": 2.06,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "10633 landed of 10924 scheduled in 12 months"
           },
           "cancellations": {
             "points": 10.0,
             "percentile": 79.7,
             "weight_pct": 12.5,
             "value": 0.0256,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 2.6,
             "note": "279 cancelled, 12 diverted"
           },
           "fare premium": {
             "points": 8.1,
             "percentile": 64.5,
             "weight_pct": 12.5,
             "value": 1.057,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 3.5,
             "percentile": 7.0,
             "weight_pct": 50.0,
             "value": -27.5,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "883.0 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "Low",
         "confidence_reasons": [
           "only 8 market(s) in DOT Table 1a (fewer than 10)"
         ]
       },
       {
         "code": "MHT",
         "name": "Manchester-Boston Regional Airport",
         "state": "NH",
         "rank": 7,
         "national_rank": 130,
         "score": 17.8,
         "score_before_friction": 17.8,
         "signals": {
           "delay": {
             "points": 2.3,
             "percentile": 9.1,
             "weight_pct": 25.0,
             "value": 1.35,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "5843 landed of 5992 scheduled in 12 months"
           },
           "cancellations": {
             "points": 9.1,
             "percentile": 73.2,
             "weight_pct": 12.5,
             "value": 0.0236,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 2.4,
             "note": "141 cancelled, 8 diverted"
           },
           "fare premium": {
             "points": 3.7,
             "percentile": 29.7,
             "weight_pct": 12.5,
             "value": 0.942,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 2.7,
             "percentile": 5.4,
             "weight_pct": 50.0,
             "value": -29.2,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "3071.1 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       }
     ],
     "not_ranked": [
       {
         "code": "HVN",
         "name": "Tweed New Haven Airport",
         "reason": "no measured delay data"
       }
     ],
     "method": "score = sum of each signal's percentile (0-100, across all airports ranked nationally) times its weight, minus the largest friction penalty, never below 0; settings from config/scoring.yaml"
   }
   ```

   </details>

### Answer

Based on the data, **Boston Logan (BOS)** and **Bangor (BGR)** are the top-scoring terminal expansion candidates in New England, though Bangor and several others are flagged for low confidence due to limited or missing data in specific categories.

Here is the ranking of New England airports:

| Rank | Airport | Score | National Rank | Delay Min/Flight | Cancellations | Passenger Growth | Fare Premium | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | BOS (Boston) | 48.2 | 77 | 6.88 (96.4th pct) | 2.8% (86.2nd pct) | -10.2% | 0.959 | High |
| 2 | BGR (Bangor) | 46.0 | 85 | 2.31 (43.5th pct) | 3.4% (95.7th pct) | Missing | 0.437 | Low* |
| 3 | BTV (Burlington) | 36.3 | 100 | 3.02 (76.1st pct) | 2.9% (88.4th pct) | -56.3% | 0.984 | Low* |
| 4 | PVD (Providence) | 34.7 | 106 | 2.13 (35.5th pct) | 2.7% (81.9th pct) | -2.9% | 0.869 | High |
| 5 | BDL (Hartford) | 32.0 | 113 | 2.43 (51.4th pct) | 2.4% (72.5th pct) | -22.8% | 0.996 | High |
| 6 | PWM (Portland) | 29.5 | 116 | 2.06 (31.9th pct) | 2.6% (79.7th pct) | -27.5% | 1.057 | Low* |
| 7 | MHT (Manchester) | 17.8 | 130 | 1.35 (9.1st pct) | 2.4% (73.2nd pct) | -29.2% | 0.942 | High |

*Note: Tweed New Haven Airport (HVN) was not ranked because it lacks measured delay data.*

**Low Confidence Flags:**
*   **BGR (Bangor):** Missing growth data (no 2019 Q1 DOT Table 1a rows) and only has 2 markets in DOT Table 1a (fewer than 10).
*   **BTV (Burlington):** Has only 3 markets in DOT Table 1a.
*   **PWM (Portland):** Has only 8 markets in DOT Table 1a.

### Assumptions and Data
*   **Preset and Weights:** Balanced (Delay: 25.0%, Cancellations: 12.5%, Fare Premium: 12.5%, Growth: 50.0%).
*   **Delay Data:** NAS delay minutes per landed flight. Source: BTS On-Time Performance (Reporting Carrier), as of Aug 2025 to Jul 2026.
*   **Cancellations:** Cancelled ÷ (scheduled − diverted). Source: BTS On-Time Performance (Reporting Carrier), as of Aug 2025 to Jul 2026.
*   **Fare Premium:** Ratio to national fare per mile (1.0 = normal fares for those distances). Source: DOT Consumer Airfare Report, Table 1a, as of 2026 Q1.
*   **Growth:** % change in passengers per day. Source: DOT Consumer Airfare Report, Table 1a, as of 2026 Q1 vs 2019 Q1.

### Run

- Seconds: 14.1
- Tokens: 3,415 in / 944 out / 330 thinking
- Cost: $0.0221
- Number check: all numbers found in tool results
