# Design: Airport Investment Intelligence Agent

<!-- You write this document (Step 8). Keep it short: 2–3 pages. Delete these comments as you fill it. -->

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
<!-- Diagram: chat UI → server → Gemini (function calling) → tools → scoring (pure) ← data layer (cache) ← public APIs. -->

## Data sources
<!-- Each source: what it gives, coverage, freshness, known gaps (e.g. no Alaska in DOT fare data). -->

## Scoring methodology
<!-- Signals, normalization, weights, presets, confidence, tie-breaking. A worked example for one airport. -->

## Where and how AI is used
<!-- What the model does (understand, choose tools, explain) vs. what code does (every number). Guardrails. -->

## Key tradeoffs
<!-- From docs/DECISIONS.md. -->

## Assumptions, uncertainty and limitations
<!-- What the scores can't tell you; when to distrust an answer. -->

## What I'd do next
<!-- Paid data, T-100 load factors, backtesting the KPI against past expansions, … -->
