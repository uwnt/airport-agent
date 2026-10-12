# c-anchorage-long-haul

Model: `gemini-3.1-pro-preview`. Run on 2026-10-11.

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

At Anchorage (Ted Stevens Anchorage International Airport), 59.9% of passenger departures are long-haul (over 1,400 miles). 

This accounts for 206 out of 344 passenger-airline departures that had a known destination during the measured period. There were 74 flights with no destination and 0 with no coordinates, which were not counted.

### Assumptions and data
* **Definition:** Passenger-airline departures flying over 1,400 miles great-circle, divided by those with a known destination; destinations 100 miles or closer and same-airport returns dropped. 
* **Data Source:** OpenSky Network (estimated destinations) (https://opensky-network.org/api/flights/departure), as of 2026-10-04 to 2026-10-10.

### Run

- Seconds: 8.9
- Tokens: 3,424 in / 215 out / 577 thinking
- Cost: $0.0164
- Number check: all numbers found in tool results
