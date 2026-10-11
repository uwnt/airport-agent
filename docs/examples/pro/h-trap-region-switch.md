# h-trap-region-switch

Model: `gemini-3.1-pro-preview`. Run on 2026-10-11.

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

Here is the ranking of New England airports for terminal expansion based on a balanced assessment of demand pressure and constraints.

### New England Airport Rankings

1. **Boston Logan International (BOS)**
   * **Score:** 48.2
   * **National Rank:** 77
   * *Notes:* Highest in the region, driven by significant delays (6.88 minutes per landed flight, 96.4th percentile). 

2. **Bangor International (BGR)**
   * **Score:** 46.0
   * **National Rank:** 85
   * *Notes:* **Low confidence** flag because growth data since 2019 Q1 is missing, and it has fewer than 10 markets in DOT fare data. Fares are low (ratio of 0.437).

3. **Patrick Leahy Burlington International (BTV)**
   * **Score:** 36.3
   * **National Rank:** 100
   * *Notes:* **Low confidence** flag due to limited DOT market coverage (only 3 markets). Growth is deeply negative (-56.3% passengers per day since 2019).

4. **Rhode Island T. F. Green International (PVD)**
   * **Score:** 34.7
   * **National Rank:** 106

5. **Bradley International (BDL)**
   * **Score:** 32.0
   * **National Rank:** 113

6. **Portland International Jetport (PWM)**
   * **Score:** 29.5
   * **National Rank:** 116
   * *Notes:* **Low confidence** flag due to limited DOT market coverage (only 8 markets). Fares are relatively high (1.057 ratio).

7. **Manchester-Boston Regional (MHT)**
   * **Score:** 17.8
   * **National Rank:** 130
   * *Notes:* Lowest score in the region, reflecting minimal delay (1.35 minutes per landed flight, 9.1st percentile) and negative growth (-29.2%).

**Not Ranked:** Tweed New Haven Airport (HVN) could not be ranked because there is no measured delay data available.

### Assumptions and data
* **Preset:** balanced
* **Weights:** delay 25.0%, cancellations 12.5%, fare premium 12.5%, growth 50.0%
* **Thresholds/Definitions:** Score is the sum of each signal's percentile (0-100, across all airports ranked nationally) times its weight, minus the largest friction penalty, never below 0. The fare premium ratio measures normal fares for those distances (1.0 = normal).
* **Sources:**
  * BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/): as of Aug 2025 to Jul 2026 (Delay and Cancellations)
  * DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json): as of 2026 Q1 and 2026 Q1 vs 2019 Q1 (Fare premium and Growth)

### Run

- Seconds: 11.9
- Tokens: 3,379 in / 742 out / 342 thinking
- Cost: $0.0198
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
     "ranked_nationally": 138,
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
             "percentile": 5.8,
             "weight_pct": 25.0,
             "value": 1.2,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "25629 landed of 25849 scheduled in 12 months"
           },
           "cancellations": {
             "points": 1.7,
             "percentile": 13.8,
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
             "percentile": 30.4,
             "weight_pct": 12.5,
             "value": 0.944,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 25.2,
             "percentile": 50.4,
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
             "percentile": 17.4,
             "weight_pct": 25.0,
             "value": 1.64,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "29489 landed of 29943 scheduled in 12 months"
           },
           "cancellations": {
             "points": 3.7,
             "percentile": 29.3,
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
             "percentile": 31.5,
             "weight_pct": 12.5,
             "value": 0.947,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 17.4,
             "percentile": 34.9,
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
             "percentile": 32.6,
             "weight_pct": 25.0,
             "value": 2.09,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "188023 landed of 190125 scheduled in 12 months"
           },
           "cancellations": {
             "points": 2.7,
             "percentile": 21.7,
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
             "percentile": 38.4,
             "weight_pct": 12.5,
             "value": 0.972,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 6.2,
             "percentile": 12.4,
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
             "percentile": 2.9,
             "weight_pct": 25.0,
             "value": 0.93,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "15035 landed of 15114 scheduled in 12 months"
           },
           "cancellations": {
             "points": 0.4,
             "percentile": 2.9,
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
             "percentile": 20.7,
             "weight_pct": 12.5,
             "value": 0.86,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 9.7,
             "percentile": 19.4,
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
             "percentile": 23.2,
             "weight_pct": 25.0,
             "value": 1.75,
             "unit": "NAS delay minutes per landed flight",
             "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
             "as_of": "Aug 2025 to Jul 2026",
             "note": "44681 landed of 45231 scheduled in 12 months"
           },
           "cancellations": {
             "points": 2.4,
             "percentile": 18.8,
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
             "percentile": 61.2,
             "weight_pct": 12.5,
             "value": 1.052,
             "unit": "ratio to national fare per mile",
             "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
             "as_of": "2026 Q1",
             "note": "1.0 = normal fares for those distances"
           },
           "growth": {
             "points": 14.7,
             "percentile": 29.5,
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

Here is the ranking of Los Angeles area airports for terminal expansion, based on a balanced assessment of demand pressure and constraints.

### LA Area Airport Rankings

1. **Ontario International (ONT)**
   * **Score:** 32.2
   * **National Rank:** 112
   * *Notes:* Leads the region primarily due to positive passenger growth (11.0% change in passengers per day since 2019, ranking in the 50.4th percentile for growth). Operational delays are very low (1.2 minutes per landed flight).

2. **Hollywood Burbank/Bob Hope (BUR)**
   * **Score:** 29.4
   * **National Rank:** 117
   * *Notes:* Also showed positive growth since 2019 (+2.4%). 

3. **Los Angeles International (LAX)**
   * **Score:** 21.9
   * **National Rank:** 127
   * *Notes:* Passenger volume remains below 2019 levels (-21.1%). Delays are moderate at 2.09 minutes per landed flight (32.6th percentile).

4. **Long Beach International (LGB)**
   * **Score:** 13.4
   * **National Rank:** 134
   * *Notes:* Very low delays and cancellations (0.42%). Passengers are down 9.3% relative to 2019.

5. **John Wayne Orange County International (SNA)**
   * **Score:** 0.5
   * **National Rank:** 138
   * *Notes:* Although SNA generated a base score of 30.5, it received a significant **friction penalty** (-30 points) due to a hard passenger cap. The settlement agreement caps passengers at 11.8 million through 2025 and 12.2 to 12.5 million through 2030. Fares here are relatively high compared to the region (1.052 ratio, 61.2nd percentile). *Note: The friction penalty may be subject to future changes; the agreement runs to 31 Dec 2030 (checked 2026-10-11).*

### Assumptions and data
* **Preset:** balanced
* **Weights:** delay 25.0%, cancellations 12.5%, fare premium 12.5%, growth 50.0%
* **Thresholds/Definitions:** Score is the sum of each signal's percentile (0-100, across all airports ranked nationally) times its weight, minus the largest friction penalty, never below 0. The fare premium ratio measures normal fares for those distances (1.0 = normal).
* **Sources:**
  * BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/): as of Aug 2025 to Jul 2026 (Delay and Cancellations)
  * DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json): as of 2026 Q1 and 2026 Q1 vs 2019 Q1 (Fare premium and Growth)

### Run

- Seconds: 11.0
- Tokens: 4,963 in / 742 out / 144 thinking
- Cost: $0.0206
- Number check: all numbers found in tool results
