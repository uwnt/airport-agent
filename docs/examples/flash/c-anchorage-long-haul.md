# c-anchorage-long-haul

Model: `gemini-3.8-flash`. Run on 2026-10-11.

## Question 1

> What share of Anchorage's passenger departures are long-haul?

### Tool calls (1)

1. `long_haul_share` {"code": "ANC", "threshold_miles": 1400}

   - ANC: 59.9% over 1,400 miles (OpenSky Network (estimated destinations) (https://opensky-network.org/api/flights/departure), 2026-10-04 to 2026-10-10)

   <details><summary>Full result</summary>

   ```json
   {
     "code": "ANC",
     "name": "Ted Stevens Anchorage International Airport",
     "available": true,
     "threshold_miles": 1400,
     "definition": "passenger-airline departures flying over 1,400 miles great-circle, divided by those with a known destination; destinations 100 miles or closer and same-airport returns dropped",
     "long_haul_share": {
       "value": 0.599,
       "unit": "share of passenger departures",
       "source": "OpenSky Network (estimated destinations) (https://opensky-network.org/api/flights/departure)",
       "as_of": "2026-10-04 to 2026-10-10",
       "value_pct": 59.9,
       "note": "206 of 344 with a known destination; 74 with no destination and 0 with no coordinates not counted"
     }
   }
   ```

   </details>

### Answer

**59.9%** of passenger departures from Ted Stevens Anchorage International Airport (ANC) are long-haul (over 1,400 miles).

### Supporting Data

| Metric | Value |
| :--- | :--- |
| **Long-haul departure share** | 59.9% (0.599) |
| **Qualifying flights** | 206 of 344 with a known destination |
| **Excluded flights** | 74 with no destination; 0 with no coordinates |

### Assumptions and data
- **Threshold & Definition:** Passenger-airline departures flying over 1,400 miles great-circle, divided by those with a known destination; destinations 100 miles or closer and same-airport returns dropped.
- **Data Source:** OpenSky Network (estimated destinations) (https://opensky-network.org/api/flights/departure), as of 2026-10-04 to 2026-10-10.

### Run

- Seconds: 9.3
- Tokens: 3,319 in / 251 out / 0 thinking
- Cost: $0.0034
- Number check: all numbers found in tool results
