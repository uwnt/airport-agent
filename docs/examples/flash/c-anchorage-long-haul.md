# c-anchorage-long-haul

Model: `gemini-3.8-flash`. Run on 2026-10-12.

## Question 1

> What share of Anchorage's passenger departures are long-haul?

### Tool calls (1)

1. `long_haul_share` {"threshold_miles": 1400, "code": "ANC"}

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

At Ted Stevens Anchorage International Airport (ANC), **59.9%** of passenger departures are long-haul (flying over 1,400 miles).

### Supporting details

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Long-haul share** | 59.9% (value: 0.599) | 206 of 344 passenger departures with a known destination (74 departures with no destination and 0 with no coordinates were not counted) |

### Assumptions and data
- **Definition & threshold**: Passenger-airline departures flying over 1,400 miles great-circle, divided by those with a known destination; destinations 100 miles or closer and same-airport returns dropped (threshold: 1,400 miles).
- **Data source**: OpenSky Network (estimated destinations) (`https://opensky-network.org/api/flights/departure`), as of `2026-10-04 to 2026-10-10`.

### Run

- Seconds: 4.2
- Tokens (reported): 3,978 in / 261 out / 111 thinking
- Tool-result input tokens (estimated): 202
- Cost (reported): $0.0044
- Cost (estimated with tool results): $0.0045
- Number check: all numbers found in tool results
