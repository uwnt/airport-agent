# Design: Airport Investment Intelligence Agent

## Problem and scope
**Who it's for.** An investment analyst making a first-pass shortlist: narrowing about 138 US
airports down to the few worth deeper due diligence. The tool shows where to look; it doesn't make
the investment call.

**What "promising" means here.** Terminal expansion pays off where two things are true at once: the
airport is already under strain now (delays from the airport and airspace, cancellations, fares
above similar-distance markets), and demand is still growing (passengers per day compared with the
same quarter of 2019). The score combines the two.

**Which airports.** Commercial airports in DOT's fare data (Table 1a), lower 48 only. That data has
no Anchorage rows, and ranking airports with missing signals would make the ranks unfair, so Alaska
and Hawaii aren't ranked. Anchorage gets one answer only: its long-haul share, from OpenSky flight
data.

**What it won't do.** Return on investment in dollars, cargo economics, financing, airline strategy
and construction cost. The agent says these are out of scope and offers what it can do instead.

**The main point.** Every number comes from a tested, deterministic tool working on public data.
The AI only reads the question and explains the results.

## Architecture
```
Chat page (plain HTML + JS, no build step)
   │  question                         ▲ steps + answer, streamed
   ▼                                   │
FastAPI server (server.py)
   │
   ▼
Gemini Flash, with tools (llm.py — our own short loop, no agent framework)
   │  picks a tool and its arguments
   ▼
Tools (tools.py) ──► Scoring (scoring.py: pure, no network, no model)
                         ▲
                    Data layer: a dated snapshot committed in the repo
                         ▲
                    Public sources: DOT, BTS, OpenSky, OurAirports
```

**How a question flows.** The page sends the question to the server, which passes it to Gemini
with a list of tools. Gemini chooses a tool, our code runs it and hands back the result, and this
repeats (at most 8 tool calls) until it can answer. The page shows each step as it happens, then
the answer.

**Why it's built this way.**
- **Own loop, no framework (D2):** the whole loop fits in one file, so nothing is hidden and every
  step can be checked.
- **All model calls in `llm.py` (D3):** the model can be swapped without touching the rest.
- **Tables come from tool results:** ranking tables on screen are drawn from the tools' output,
  not the model's text, so a number can't be retyped wrongly.
- **Snapshot in the repo:** anyone gets the same numbers without keys for the data sources.

**Running it.** One Docker image, built and tested only in GitHub Actions, for Intel and Apple
Silicon. The same image runs locally (`docker compose up`) and on Fly.io.

## Data sources
Detail, samples and known traps are in [DATA_SOURCES.md](DATA_SOURCES.md).

| Source | What it gives us | Gaps |
|---|---|---|
| DOT Consumer Airfare Report, Table 1a | Passengers and fares by market → growth vs 2019, fare premium | Only the busiest markets, so small airports rest on part of their traffic (flagged); no Alaska rows |
| BTS On-Time Performance | Delay by cause (NAS delay) and cancellations, latest 12 months → strain | Delay is a symptom; it doesn't measure terminal space |
| OpenSky | Departures and destinations → Anchorage long-haul share | ~14% of flights have no known destination (reported, never guessed); terms limit commercial use |
| OurAirports | Codes, names, coordinates | — |

Not used: FAA ASPM (needs a login) and the FAA Terminal Area Forecast (no bulk download). Both are
in "What I'd do next".

## Scoring methodology
All numbers live in [`config/scoring.yaml`](../config/scoring.yaml), so a change needs no Python
(D9).

- **Signals (D7).** *Strain*: NAS delay minutes per landed flight (half of strain), cancellation
  rate (a quarter), fare premium versus markets of similar distance (a quarter). *Growth*:
  passengers per day versus the same quarter of 2019.
- **Normalisation (D8).** Each signal becomes a 0–100 percentile across the ranked airports; the
  score is the weighted sum.
- **Presets.** Strain/growth: balanced 50/50 (the default), growth-focused 30/70,
  congestion-focused 70/30.
- **Friction (D10).** A sourced penalty from `data/constraints.yaml`: minor 10, major 20, hard cap
  30 points; only the largest counts (SNA's passenger cap under a 1985 settlement: 30; SFO's close
  runways, which can't be spread apart without filling the Bay: 20).
- **Confidence (D12).** Low when a signal is missing (its weight moves to the others) or the
  airport has fewer than 10 markets in Table 1a.
- **Ties.** The higher score before friction wins, then alphabetical by code.

**Worked example: Boston Logan (BOS), balanced preset.**

| Signal | Value | Percentile | Weight | Points |
|---|---|---|---|---|
| NAS delay | 6.88 min per landed flight | 96 | 25% | 24.1 |
| Cancellations | 2.8% | 86 | 12.5% | 10.8 |
| Fare premium | 0.959 × national | 36 | 12.5% | 4.4 |
| Growth vs 2019 | −10.2% passengers per day | 18 | 50% | 8.9 |
| Friction | none on file | | | 0 |
| **Score** | | | | **48.2** |

BOS is #1 in New England but #77 nationally: heavily strained, yet still below 2019 traffic.
Source run: [docs/examples/flash/a-new-england.md](examples/flash/a-new-england.md).

## Where and how AI is used
- **The model (Gemini Flash)** reads the question, chooses tools and their arguments, and explains
  the results. It never computes a number.
- **Code** does every number: scoring is pure and tested, with no network and no model.
- **Guardrails.**
  - The system prompt forbids numbers that didn't come from a tool, and averages the tools don't
    give.
  - Names a tool didn't return are labelled general knowledge, and a tool's error reason is quoted.
  - Domain facts come only from [DOMAIN_NOTES.md](DOMAIN_NOTES.md), and only those marked verified
    are stated as fact, each with a date (D23).
  - At most 8 tool calls per question; a low thinking level for speed (D22).
- **Checked automatically.** A tested checker, run over every evaluation answer, confirms each
  number appears in a tool result; a test confirms each tool returns the same result twice.
- **Results (Step 7, [docs/examples/](examples/)).** Four questions and five trick questions, on
  Flash and Pro: every number was found in tool results on both. Flash: about 6 s and under one
  cent per question. Dollar ROI is declined as out of scope; a nonsense airport code gets the
  tool's error; "LA" is read as LAX.

## Key tradeoffs
- **Percentiles, not z-scores (D8).** One extreme airport (EWR's 8% cancellations) can't stretch
  everyone else's scores. Cost: a small gap and a big gap at the top look the same.
- **Free public data only, and Flash (D5, D25).** A reviewer can reproduce every number, and Flash
  costs a third of Pro (on reported tokens) with the same number accuracy. Cost: no gate or terminal capacity data.
- **Friction as a sourced penalty (D10).** Real limits (SNA's passenger cap, SFO's runways) are visible,
  dated judgement in one file, not hidden in code. Cost: it's judgement, so it needs re-checking.
- **Our own tool loop, no agent framework (D2).** Readable, nothing hidden. Cost: we wrote the loop
  and its limits ourselves.

## Assumptions, uncertainty and limitations
- **No source measures terminal capacity.** Strain is inferred from delays, cancellations and
  fares; a strained airfield can look like a strained terminal.
- **Scores are relative.** A percentile says how an airport compares, not how much it needs.
- **Thin data.** Table 1a lists only the busiest markets, so small airports rest on part of their
  traffic; those are flagged low confidence.
- **Penalties are judgement.** Each is sourced and dated, with a review date (D23).
- **The model isn't perfect.** Asked to compare LAX and SNA on congestion, Flash led with the
  balanced ranks and gave the congestion-focused ones only in a side note
  ([run](examples/flash/b-lax-vs-sna.md)). Every number stays tool-backed.

## What I'd do next
1. **Watch the fact sources automatically**, and open an issue when a penalty's evidence changes;
   add a bad-weather capacity signal from FAA capacity profiles.
2. **Paid or official data:** FAA ASPM, T-100 seats and load factors, the Terminal Area Forecast.
3. **Backtest the score** against airports that did expand, to test the measure itself.
