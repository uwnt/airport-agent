# b-lax-vs-sna

Model: `gemini-3.8-flash`. Run on 2026-10-12.

## Question 1

> How do LAX and SNA compare on congestion?

### Tool calls (4)

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
     "ranked_count": 138,
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
             "percentile": 33,
             "weight_pct": 35.0,
             "value": 2.09,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "188023 landed of 190125 scheduled in 12 months"
           },
           "cancellations": {
             "points": 3.8,
             "percentile": 22,
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
             "percentile": 38,
             "weight_pct": 17.5,
             "value": 0.972,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 3.7,
             "percentile": 12,
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
             "percentile": 23,
             "weight_pct": 35.0,
             "value": 1.75,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "44681 landed of 45231 scheduled in 12 months"
           },
           "cancellations": {
             "points": 3.3,
             "percentile": 19,
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
             "percentile": 61,
             "weight_pct": 17.5,
             "value": 1.052,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 8.8,
             "percentile": 29,
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

2. `compare_airports` {"codes": ["LAX", "SNA"], "preset": "balanced"}

   - preset balanced, weights {'delay': 25.0, 'cancellations': 12.5, 'fare premium': 12.5, 'growth': 50.0}, 138 ranked nationally
   - #1 LAX score 21.9 (national #127, High confidence)
   - #2 SNA score 0.5 (national #138, High confidence, friction -30)

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
     "region": null,
     "rows": [
       {
         "code": "LAX",
         "name": "Los Angeles International Airport",
         "state": "CA",
         "rank": 1,
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
         "code": "SNA",
         "name": "John Wayne Orange County International Airport",
         "state": "CA",
         "rank": 2,
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

3. `demand_pressure` {"code": "LAX"}

   - LAX: top quartile nationally: none; bottom quartile: cancellations, growth.
   - delay: percentile 33, value 2.09
   - cancellations: percentile 22, value 0.0099
   - fare premium: percentile 38, value 0.972
   - growth: percentile 12, value -21.1

   <details><summary>Full result</summary>

   ```json
   {
     "code": "LAX",
     "name": "Los Angeles International Airport",
     "ranked": true,
     "ranked_count": 138,
     "signals": {
       "delay": {
         "group": "strain",
         "percentile": 33,
         "value": 2.09,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "188023 landed of 190125 scheduled in 12 months"
       },
       "cancellations": {
         "group": "strain",
         "percentile": 22,
         "value": 0.0099,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 1.0,
         "note": "1877 cancelled, 225 diverted"
       },
       "fare premium": {
         "group": "strain",
         "percentile": 38,
         "value": 0.972,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth": {
         "group": "growth",
         "percentile": 12,
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
     "percentile_note": "percentile 100 = highest of the ranked_count airports ranked nationally; higher means more strain or more growth. ranked_count is how many airports are ranked, not this airport's rank: this tool gives no rank (rank_airports gives national_rank)"
   }
   ```

   </details>

4. `demand_pressure` {"code": "SNA"}

   - SNA: top quartile nationally: none; bottom quartile: delay, cancellations.
   - delay: percentile 23, value 1.75
   - cancellations: percentile 19, value 0.0091
   - fare premium: percentile 61, value 1.052
   - growth: percentile 29, value -0.7

   <details><summary>Full result</summary>

   ```json
   {
     "code": "SNA",
     "name": "John Wayne Orange County International Airport",
     "ranked": true,
     "ranked_count": 138,
     "signals": {
       "delay": {
         "group": "strain",
         "percentile": 23,
         "value": 1.75,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "44681 landed of 45231 scheduled in 12 months"
       },
       "cancellations": {
         "group": "strain",
         "percentile": 19,
         "value": 0.0091,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 0.9,
         "note": "409 cancelled, 141 diverted"
       },
       "fare premium": {
         "group": "strain",
         "percentile": 61,
         "value": 1.052,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth": {
         "group": "growth",
         "percentile": 29,
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
     "percentile_note": "percentile 100 = highest of the ranked_count airports ranked nationally; higher means more strain or more growth. ranked_count is how many airports are ranked, not this airport's rank: this tool gives no rank (rank_airports gives national_rank)"
   }
   ```

   </details>

### Answer

Both airports show relatively low operational congestion compared to the rest of the country, with both delay and cancellation rates placing below the 50th percentile nationally. Between the two, LAX experiences slightly more operational delay (2.09 NAS delay minutes per landed flight, 33rd percentile) and a slightly higher cancellation rate (1.0%, 22nd percentile) than SNA (1.75 NAS delay minutes per landed flight, 23rd percentile; 0.9% cancellation rate, 19th percentile). 

However, SNA shows stronger fare premium strain (1.052 ratio to national fare per mile, 61st percentile) than LAX (0.972 ratio, 38th percentile). In addition, SNA is subject to a 30-point passenger cap friction penalty, whereas LAX has no friction penalties on file.

Under the balanced preset:
- **LAX** ranks 127 of 138 nationally with a score of 21.9.
- **SNA** ranks 138 of 138 nationally with a score of 0.5 (score before friction: 30.5).

### Congestion & Strain Signals Comparison

| Signal | Metric / Unit | LAX Value (Percentile) | SNA Value (Percentile) |
| :--- | :--- | :--- | :--- |
| **Delay** | NAS delay minutes per landed flight | 2.09 (33rd percentile) | 1.75 (23rd percentile) |
| **Cancellations** | Cancellation rate | 1.0% (22nd percentile) | 0.9% (19th percentile) |
| **Fare premium** | Ratio to national fare per mile | 0.972 (38th percentile) | 1.052 (61st percentile) |
| **Passenger growth** | % change in passengers per day (2026 Q1 vs 2019 Q1) | -21.1% (12th percentile) | -0.7% (29th percentile) |

### Friction and Confidence
- **LAX**: Confidence is High. Friction penalty: none on file (0 points).
- **SNA**: Confidence is High. Friction penalty: 30 points for a Passenger cap (annual passenger cap under the 1985 settlement agreement as amended: 11.8 million through 2025; 12.2 million for 2026 to 2030, or 12.5 million only if 11.21 million were served in 2021 to 2025 and certain mitigation measures are met; agreement runs to 31 Dec 2030; checked 2026-10-11, review by 2030-12-31). Friction not counted: Curfew (minor, 10 points; only the largest penalty counts).

### Assumptions and data
- **Preset**: balanced
  - Weights: passenger growth 50.0%, delay 25.0%, cancellations 12.5%, fare premium 12.5%
- *(Under the congestion-focused preset, weights are delay 35.0%, growth 30.0%, cancellations 17.5%, fare premium 17.5%; under this preset, LAX scores 25.7 with national rank 126 of 138, and SNA scores 1.0 with national rank 138 of 138).*
- **Data sources**:
  - BTS On-Time Performance (Reporting Carrier) (`https://transtats.bts.gov/PREZIP/`), as of Aug 2025 to Jul 2026 (delay and cancellations).
  - DOT Consumer Airfare Report, Table 1a (`https://datahub.transportation.gov/resource/tfrh-tu9e.json`), as of 2026 Q1 (fare premium) and 2026 Q1 vs 2019 Q1 (passenger growth).

### Run

- Seconds: 10.3
- Tokens (reported): 4,287 in / 1,004 out / 335 thinking
- Tool-result input tokens (estimated): 4,402
- Cost (reported): $0.0082
- Cost (estimated with tool results): $0.0115
- Number check: all numbers found in tool results
