# d-sfo-unmet-demand

Model: `gemini-3.8-flash`. Run on 2026-10-12.

## Question 1

> Is there unmet demand at SFO, and why?

### Tool calls (2)

1. `demand_pressure` {"code": "SFO"}

   - SFO: top quartile nationally: delay; bottom quartile: cancellations, growth.
   - delay: percentile 100, value 9.84
   - cancellations: percentile 25, value 0.0107
   - fare premium: percentile 45, value 1.005
   - growth: percentile 20, value -8.8

   <details><summary>Full result</summary>

   ```json
   {
     "code": "SFO",
     "name": "San Francisco International Airport",
     "ranked": true,
     "ranked_count": 138,
     "signals": {
       "delay": {
         "group": "strain",
         "percentile": 100,
         "value": 9.84,
         "unit": "NAS delay minutes per landed flight",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "note": "145831 landed of 147716 scheduled in 12 months"
       },
       "cancellations": {
         "group": "strain",
         "percentile": 25,
         "value": 0.0107,
         "unit": "cancelled ÷ (scheduled − diverted)",
         "source": "BTS On-Time Performance (Reporting Carrier) (https://transtats.bts.gov/PREZIP/)",
         "as_of": "Aug 2025 to Jul 2026",
         "value_pct": 1.1,
         "note": "1579 cancelled, 306 diverted"
       },
       "fare premium": {
         "group": "strain",
         "percentile": 45,
         "value": 1.005,
         "unit": "ratio to national fare per mile",
         "source": "DOT Consumer Airfare Report, Table 1a (https://datahub.transportation.gov/resource/tfrh-tu9e.json)",
         "as_of": "2026 Q1",
         "note": "1.0 = normal fares for those distances"
       },
       "growth": {
         "group": "growth",
         "percentile": 20,
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
     "percentile_note": "percentile 100 = highest of the ranked_count airports ranked nationally; higher means more strain or more growth. ranked_count is how many airports are ranked, not this airport's rank: this tool gives no rank (rank_airports gives national_rank)"
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

San Francisco International Airport (SFO) shows severe operational strain through air traffic delays, placing in the 100th percentile nationally for delays, but it does not show typical signs of unmet passenger demand across pricing or traffic growth. Its passenger volume has contracted compared to 2019 levels (placing in the 20th percentile nationally for growth), its cancellation rate is low (25th percentile), and its fares are below the 50th percentile (45th percentile).

The extreme delays at SFO stem from airfield capacity constraints during adverse weather:
* **Runway spacing and weather sensitivity:** Runways 28L and 28R are 750 ft apart (centreline to centreline). In good weather, two planes can land side by side; in instrument conditions (low cloud or fog), they cannot, and arrivals are flown as staggered pairs instead. FAA's capacity profile shows the airport's hourly rate falling from 104–107 operations (visual, side by side) to 71–78 (instrument) (Note 6, checked 2026-10-11, [FAA Order JO 7110.308B](https://www.faa.gov/documentLibrary/media/Order/2017-07-10_JO_7110.308B_Simultaneous_Dependent_Approaches_to_Closely_Parallel_Runways.pdf), [FAA Airport Capacity Profile](https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/SFO-Airport-Capacity-Profile-2019.pdf)).
* **Runway expansion barriers:** SFO cannot widen the runway gap without Bay fill. The Bay Conservation and Development Commission (BCDC) issues Bay fill permits under the McAteer-Petris Act. A 1999 runway reconfiguration plan considered up to about 1,500 acres of fill; in 2001, San Francisco voters passed Proposition D, requiring a public vote for any city project with more than 100 acres of Bay fill. The runways were never moved (Note 7, checked 2026-10-11, [Federal Register Notice](https://www.govinfo.gov/content/pkg/FR-1999-07-01/html/99-16756.htm), [SF Board of Supervisors](https://sfbos.org/introduction-4), [CEQA Net](https://ceqanet.lci.ca.gov/1999072002)).

### Measured Demand and Strain Signals (SFO)

| Signal | Group | Measured Value | National Percentile | Source | As of |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Delay** | Strain | 9.84 NAS delay minutes per landed flight | 100th | BTS On-Time Performance | Aug 2025 to Jul 2026 |
| **Cancellations** | Strain | 1.1% (0.0107 cancelled ÷ [scheduled − diverted]) | 25th | BTS On-Time Performance | Aug 2025 to Jul 2026 |
| **Fare Premium** | Strain | 1.005 ratio to national fare per mile | 45th | DOT Consumer Airfare Report, Table 1a | 2026 Q1 |
| **Growth** | Growth | -8.8% change in passengers per day | 20th | DOT Consumer Airfare Report, Table 1a | 2026 Q1 vs 2019 Q1 |

### Friction and Confidence
* **Friction Penalty:** Applied under tier "major" (20 points) for "Runway spacing and Bay fill" (checked 2026-10-11, review by 2027-10-11).
* **Confidence:** High.

### Assumptions and data
* **Definitions:**
  * National percentiles are calculated out of 138 ranked airports nationally (percentile 100 indicates the highest value).
  * Fare premium: ratio of 1.0 represents normal fares for those distances.
  * Growth: measured as passenger-per-day change in 2026 Q1 relative to 58,683.3 passengers per day in 2019 Q1.
* **Sources and Dates:**
  * Bureau of Transportation Statistics (BTS) On-Time Performance (Reporting Carrier): August 2025 to July 2026 (145,831 landed of 147,716 scheduled flights; 1,579 cancelled, 306 diverted).
  * Department of Transportation (DOT) Consumer Airfare Report, Table 1a: 2026 Q1 and 2019 Q1.

### Run

- Seconds: 7.6
- Tokens (reported): 3,876 in / 1,135 out / 0 thinking
- Tool-result input tokens (estimated): 2,325
- Cost (reported): $0.0072
- Cost (estimated with tool results): $0.0089
- Number check: all numbers found in tool results
