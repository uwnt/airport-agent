# b-lax-vs-sna

Model: `gemini-3.1-pro-preview`. Run on 2026-10-11.

## Question 1

> How do LAX and SNA compare on congestion?

### Tool calls (1)

1. `compare_airports` {"preset": "congestion-focused", "codes": ["LAX", "SNA"]}

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

### Answer

When comparing Los Angeles International (LAX) and John Wayne Orange County (SNA) with a focus on congestion, both airports rank relatively low nationally for unmet demand signals. LAX currently has a higher final score than SNA, but this is primarily due to a severe regulatory friction penalty at SNA. 

Before accounting for friction, SNA actually shows slightly higher congestion-focused demand (score 31.0) compared to LAX (score 25.7), driven by its higher fare premium and passenger volume recovery. However, SNA is subject to a hard passenger cap which deducts 30 points, bringing its final score down to 1.0.

Here is the side-by-side breakdown of the underlying signals:

| Metric | LAX | SNA |
| :--- | :--- | :--- |
| **Final Score (out of 100)** | 25.7 | 1.0 |
| **National Rank** | 126 | 138 |
| **Delay** | 2.09 minutes (32.6th percentile) | 1.75 minutes (23.2nd percentile) |
| **Cancellations** | 1.0% (21.7th percentile) | 0.9% (18.8th percentile) |
| **Fare Premium** | 0.972 ratio (38.4th percentile) | 1.052 ratio (61.2th percentile) |
| **Passenger Growth** | -21.1% (12.4th percentile) | -0.7% (29.5th percentile) |

**Friction Penalties**
*   **SNA:** Subject to a "Passenger cap" penalty (-30 points). The final score dropped from 31.0 to 1.0. SNA also has a minor "Curfew" penalty (10 points) which is not counted, as only the largest penalty is applied.
*   **LAX:** None on file.
*   Both airports have High confidence in their data.

### Assumptions and data
*   **Preset:** congestion-focused
*   **Weights:** delay (35.0%), cancellations (17.5%), fare premium (17.5%), growth (30.0%)
*   **Delay:** NAS delay minutes per landed flight. Source: BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/) as_of Aug 2025 to Jul 2026
*   **Cancellations:** cancelled ÷ (scheduled − diverted). Source: BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/) as_of Aug 2025 to Jul 2026
*   **Fare Premium:** ratio to national fare per mile. Source: DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json) as_of 2026 Q1
*   **Growth:** % change in passengers per day. Source: DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json) as_of 2026 Q1 vs 2019 Q1

### Run

- Seconds: 16.2
- Tokens: 3,410 in / 767 out / 423 thinking
- Cost: $0.0211
- Number check: all numbers found in tool results
