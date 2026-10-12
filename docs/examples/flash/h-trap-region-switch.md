# h-trap-region-switch

Model: `gemini-3.8-flash`. Run on 2026-10-12.

## Question 1

> Rank the New England airports.

### Tool calls (1)

1. `rank_airports` {"region": "New England"}

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
     "ranked_count": 138,
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
             "percentile": 96,
             "weight_pct": 25.0,
             "value": 6.88,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "139256 landed of 143441 scheduled in 12 months"
           },
           "cancellations": {
             "points": 10.8,
             "percentile": 86,
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
             "percentile": 36,
             "weight_pct": 12.5,
             "value": 0.959,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 8.9,
             "percentile": 18,
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
             "percentile": 43,
             "weight_pct": 50.0,
             "value": 2.31,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "3836 landed of 3984 scheduled in 12 months"
           },
           "cancellations": {
             "points": 23.9,
             "percentile": 96,
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
             "percentile": 1,
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
             "percentile": 76,
             "weight_pct": 25.0,
             "value": 3.02,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "5884 landed of 6084 scheduled in 12 months"
           },
           "cancellations": {
             "points": 11.1,
             "percentile": 88,
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
             "percentile": 41,
             "weight_pct": 12.5,
             "value": 0.984,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 1.2,
             "percentile": 2,
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
             "percentile": 36,
             "weight_pct": 25.0,
             "value": 2.13,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "15152 landed of 15593 scheduled in 12 months"
           },
           "cancellations": {
             "points": 10.2,
             "percentile": 82,
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
             "percentile": 22,
             "weight_pct": 12.5,
             "value": 0.869,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 12.8,
             "percentile": 26,
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
             "percentile": 51,
             "weight_pct": 25.0,
             "value": 2.43,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "21777 landed of 22344 scheduled in 12 months"
           },
           "cancellations": {
             "points": 9.1,
             "percentile": 72,
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
             "percentile": 43,
             "weight_pct": 12.5,
             "value": 0.996,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 4.7,
             "percentile": 9,
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
             "percentile": 32,
             "weight_pct": 25.0,
             "value": 2.06,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "10633 landed of 10924 scheduled in 12 months"
           },
           "cancellations": {
             "points": 10.0,
             "percentile": 80,
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
             "percentile": 64,
             "weight_pct": 12.5,
             "value": 1.057,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 3.5,
             "percentile": 7,
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
             "percentile": 9,
             "weight_pct": 25.0,
             "value": 1.35,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "5843 landed of 5992 scheduled in 12 months"
           },
           "cancellations": {
             "points": 9.1,
             "percentile": 73,
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
             "percentile": 30,
             "weight_pct": 12.5,
             "value": 0.942,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 2.7,
             "percentile": 5,
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

Boston Logan International Airport (BOS) ranks highest among New England airports for terminal expansion with an overall score of 48.2 (national rank 77 of 138), followed by Bangor International Airport (BGR) and Patrick Leahy Burlington International Airport (BTV). Tweed New Haven Airport (HVN) is not ranked due to having no measured delay data.

### New England Airport Rankings

| Regional Rank | Airport Code | Airport Name | State | Score | National Rank (of 138) | Friction Penalty | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | BOS | Boston Logan International Airport | MA | 48.2 | 77 | 0 | High |
| 2 | BGR | Bangor International Airport | ME | 46.0 | 85 | 0 | Low |
| 3 | BTV | Patrick Leahy Burlington International Airport | VT | 36.3 | 100 | 0 | Low |
| 4 | PVD | Rhode Island T. F. Green International Airport | RI | 34.7 | 106 | 0 | High |
| 5 | BDL | Bradley International Airport | CT | 32.0 | 113 | 0 | High |
| 6 | PWM | Portland International Jetport | ME | 29.5 | 116 | 0 | Low |
| 7 | MHT | Manchester-Boston Regional Airport | NH | 17.8 | 130 | 0 | High |

### Confidence Flags and Friction
- **Low confidence flags:**
  - **BGR:** Growth signal is missing (no DOT Table 1a rows for 2019 Q1), and only 2 markets are present in DOT Table 1a (fewer than 10).
  - **BTV:** Only 3 markets in DOT Table 1a (fewer than 10).
  - **PWM:** Only 8 markets in DOT Table 1a (fewer than 10).
- **Friction penalties:** None on file for any ranked New England airport (penalty points: 0).

---

### Assumptions and data
- **Preset:** balanced
- **Weights:**
  - Growth: 50.0%
  - Delay: 25.0%
  - Cancellations: 12.5%
  - Fare premium: 12.5%
- **Scoring Method:** Score = sum of each signal's percentile (0–100, across all airports ranked nationally) times its weight, minus the largest friction penalty, never below 0.
- **Data Sources:**
  - **BTS On-Time Performance (Reporting Carrier):** Delay (NAS delay minutes per landed flight) and Cancellations (cancelled ÷ [scheduled − diverted]), as of Aug 2025 to Jul 2026.
  - **DOT Consumer Airfare Report, Table 1a:** Fare premium (ratio to national fare per mile, where 1.0 = normal fares for those distances), as of 2026 Q1.
  - **DOT Consumer Airfare Report, Table 1a:** Growth (% change in passengers per day), as of 2026 Q1 vs 2019 Q1.

### Run

- Seconds: 6.5
- Tokens (reported): 3,843 in / 761 out / 0 thinking
- Tool-result input tokens (estimated): 4,196
- Cost (reported): $0.0057
- Cost (estimated with tool results): $0.0089
- Number check: all numbers found in tool results

## Question 2

> Now do the same for the LA area.

### Tool calls (1)

1. `rank_airports` {"region": "LA area"}

   - preset balanced, weights {'delay': 25.0, 'cancellations': 12.5, 'fare premium': 12.5, 'growth': 50.0}, 138 ranked nationally
   - #1 ONT score 32.2 (national #112, High confidence)
   - #2 BUR score 29.4 (national #117, High confidence)
   - #3 LAX score 21.9 (national #127, High confidence)
   - #4 LGB score 13.4 (national #134, High confidence)
   - #5 SNA score 0.5 (national #138, High confidence, friction -30)

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
     "ranked_count": 138,
     "region": "LA area",
     "rows": [
       {
         "code": "ONT",
         "name": "Ontario International Airport",
         "state": "CA",
         "rank": 1,
         "national_rank": 112,
         "score": 32.2,
         "score_before_friction": 32.2,
         "signals": {
           "delay": {
             "points": 1.4,
             "percentile": 6,
             "weight_pct": 25.0,
             "value": 1.2,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "25629 landed of 25849 scheduled in 12 months"
           },
           "cancellations": {
             "points": 1.7,
             "percentile": 14,
             "weight_pct": 12.5,
             "value": 0.008,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 0.8,
             "note": "206 cancelled, 14 diverted"
           },
           "fare premium": {
             "points": 3.8,
             "percentile": 30,
             "weight_pct": 12.5,
             "value": 0.944,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 25.2,
             "percentile": 50,
             "weight_pct": 50.0,
             "value": 11.0,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "9829.0 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       },
       {
         "code": "BUR",
         "name": "Hollywood Burbank/Bob Hope Airport",
         "state": "CA",
         "rank": 2,
         "national_rank": 117,
         "score": 29.4,
         "score_before_friction": 29.4,
         "signals": {
           "delay": {
             "points": 4.3,
             "percentile": 17,
             "weight_pct": 25.0,
             "value": 1.64,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "29489 landed of 29943 scheduled in 12 months"
           },
           "cancellations": {
             "points": 3.7,
             "percentile": 29,
             "weight_pct": 12.5,
             "value": 0.0117,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 1.2,
             "note": "348 cancelled, 106 diverted"
           },
           "fare premium": {
             "points": 3.9,
             "percentile": 32,
             "weight_pct": 12.5,
             "value": 0.947,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 17.4,
             "percentile": 35,
             "weight_pct": 50.0,
             "value": 2.4,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "11129.8 per day in 2019 Q1"
           }
         },
         "friction": {
           "name": "none on file",
           "points": 0
         },
         "confidence": "High"
       },
       {
         "code": "LAX",
         "name": "Los Angeles International Airport",
         "state": "CA",
         "rank": 3,
         "national_rank": 127,
         "score": 21.9,
         "score_before_friction": 21.9,
         "signals": {
           "delay": {
             "points": 8.2,
             "percentile": 33,
             "weight_pct": 25.0,
             "value": 2.09,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "188023 landed of 190125 scheduled in 12 months"
           },
           "cancellations": {
             "points": 2.7,
             "percentile": 22,
             "weight_pct": 12.5,
             "value": 0.0099,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 1.0,
             "note": "1877 cancelled, 225 diverted"
           },
           "fare premium": {
             "points": 4.8,
             "percentile": 38,
             "weight_pct": 12.5,
             "value": 0.972,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 6.2,
             "percentile": 12,
             "weight_pct": 50.0,
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
         "code": "LGB",
         "name": "Long Beach International Airport",
         "state": "CA",
         "rank": 4,
         "national_rank": 134,
         "score": 13.4,
         "score_before_friction": 13.4,
         "signals": {
           "delay": {
             "points": 0.7,
             "percentile": 3,
             "weight_pct": 25.0,
             "value": 0.93,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "15035 landed of 15114 scheduled in 12 months"
           },
           "cancellations": {
             "points": 0.4,
             "percentile": 3,
             "weight_pct": 12.5,
             "value": 0.0042,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 0.4,
             "note": "63 cancelled, 16 diverted"
           },
           "fare premium": {
             "points": 2.6,
             "percentile": 21,
             "weight_pct": 12.5,
             "value": 0.86,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 9.7,
             "percentile": 19,
             "weight_pct": 50.0,
             "value": -9.3,
             "unit": "% change in passengers per day",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1 vs 2019 Q1",
             "note": "6850.6 per day in 2019 Q1"
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
         "rank": 5,
         "national_rank": 138,
         "score": 0.5,
         "score_before_friction": 30.5,
         "signals": {
           "delay": {
             "points": 5.8,
             "percentile": 23,
             "weight_pct": 25.0,
             "value": 1.75,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "44681 landed of 45231 scheduled in 12 months"
           },
           "cancellations": {
             "points": 2.4,
             "percentile": 19,
             "weight_pct": 12.5,
             "value": 0.0091,
             "unit": "cancelled ÷ (scheduled − diverted)",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "value_pct": 0.9,
             "note": "409 cancelled, 141 diverted"
           },
           "fare premium": {
             "points": 7.7,
             "percentile": 61,
             "weight_pct": 12.5,
             "value": 1.052,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 14.7,
             "percentile": 29,
             "weight_pct": 50.0,
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

### Answer

Ontario International Airport (ONT) ranks highest among LA area airports for terminal expansion with an overall score of 32.2 (national rank 112 of 138), followed by Hollywood Burbank/Bob Hope Airport (BUR) and Los Angeles International Airport (LAX). John Wayne Orange County International Airport (SNA) ranks 5th locally (national rank 138 of 138) after a 30-point friction penalty.

### LA Area Airport Rankings

| Regional Rank | Airport Code | Airport Name | State | Score | Score Before Friction | National Rank (of 138) | Friction Penalty | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | ONT | Ontario International Airport | CA | 32.2 | 32.2 | 112 | 0 | High |
| 2 | BUR | Hollywood Burbank/Bob Hope Airport | CA | 29.4 | 29.4 | 117 | 0 | High |
| 3 | LAX | Los Angeles International Airport | CA | 21.9 | 21.9 | 127 | 0 | High |
| 4 | LGB | Long Beach International Airport | CA | 13.4 | 13.4 | 134 | 0 | High |
| 5 | SNA | John Wayne Orange County International Airport | CA | 0.5 | 30.5 | 138 | 30 | High |

### Confidence and Friction Details
- **Confidence:** All 5 airports have High confidence ratings.
- **Friction Penalties:**
  - **SNA:** Receives a 30-point friction penalty for a "Passenger cap" (checked 2026-10-11, review_by 2030-12-31; sources: https://www.ocair.com/about/administration/settlement-agreement/key-provisions-settlement-agreement and https://www.ocair.com/about/administration/settlement-agreement/settlement-agreement-faqs). SNA also has an uncounted friction entry: "Curfew (minor, 10 points; only the largest penalty counts)".
  - **ONT, BUR, LAX, LGB:** None on file (0 points).

---

### Assumptions and data
- **Preset:** balanced
- **Weights:**
  - Growth: 50.0%
  - Delay: 25.0%
  - Cancellations: 12.5%
  - Fare premium: 12.5%
- **Scoring Method:** Score = sum of each signal's percentile (0–100, across all airports ranked nationally) times its weight, minus the largest friction penalty, never below 0.
- **Data Sources:**
  - **BTS On-Time Performance (Reporting Carrier):** Delay (NAS delay minutes per landed flight) and Cancellations (cancelled ÷ [scheduled − diverted]), as of Aug 2025 to Jul 2026.
  - **DOT Consumer Airfare Report, Table 1a:** Fare premium (ratio to national fare per mile, where 1.0 = normal fares for those distances), as of 2026 Q1.
  - **DOT Consumer Airfare Report, Table 1a:** Growth (% change in passengers per day), as of 2026 Q1 vs 2019 Q1.

### Run

- Seconds: 5.9
- Tokens (reported): 5,405 in / 801 out / 0 thinking
- Tool-result input tokens (estimated): 11,632
- Cost (reported): $0.0071
- Cost (estimated with tool results): $0.0158
- Number check: all numbers found in tool results
