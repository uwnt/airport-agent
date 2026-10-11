# Decision log

One entry per decision, newest last. Each entry is the raw material for the "Key tradeoffs" section of
`DESIGN.md`. Format:

```
## D<n>: <decision in a few words>
- Chose: …
- Over: … (why not)
- Because: …
- Revisit if: …
```

## D1: Python, uv, FastAPI
- Chose: Python 3, uv for dependencies (with lockfile), FastAPI for the web chat.
- Over: TypeScript (more code for data handling; less typical for a data/AI role), pip+venv (no
  lockfile), Streamlit (voice needs an extra service; hides the request flow).
- Because: the standard data/AI stack reviewers read fluently, and one command (`uv run`) to
  reproduce.
- Revisit if: the UI grows beyond one page.

## D2: Model tool use, no agent framework (proposed; confirm at Step 5)
- Chose: the model SDK's own tool use (function calling). The model routes and explains; code computes.
- Over: LangChain/LangGraph (heavy abstraction over ~50 lines), text-to-SQL (unchecked numbers), no
  model (fails conversational follow-up).
- Because: it gives the clearest line between AI and deterministic logic, which the brief asks us to
  explain.
- Revisit if: we need multi-step planning across many tools.

## D3: Gemini as the agent's model, behind one module
- Chose: Google Gemini (`google-genai`) for tool use, explanation and voice; every model call in
  `llm.py`; provider and model from configuration. The code is built with Claude Code.
- Over: Claude (equally strong text tool use, but no audio in or out, so voice would stay
  push-to-talk only); a mix of Claude for text and Gemini for voice (two vendors and two tool
  formats; text and voice answers could disagree); LangChain or LiteLLM (heavy, hides the
  reasoning).
- Because: Gemini's Live API allows a real voice conversation using the same tools, and we already
  have a paid account.
- Revisit if: answer quality on the four example questions is weak on both Pro and Flash, or the Live
  API proves unstable (then keep push-to-talk only).

## D4: Pin Python 3.13 everywhere
- Chose: Python 3.13, pinned in `pyproject.toml` (`==3.13.*`) and `.python-version`; uv installs it,
  CI reads `.python-version`, the Dockerfile will use the matching slim image.
- Over: 3.14 (newest and on the dev server, but some libraries and slim images lag), 3.12 (older,
  no benefit).
- Because: one version in dev, CI and Docker removes "works on my machine" differences, and 3.13 is
  the mainstream release every dependency we need supports.
- Revisit if: a dependency we need drops 3.13 support.

## D5: Free public data sources only
- Chose: DOT Airfare Report, BTS enplanements and on-time data, FAA NAS Status, OurAirports, and
  OpenSky (free account).
- Over: commercial flight APIs (Aviationstack, FlightAware, Cirium). Their free tiers have no flight
  history, no route data, no commercial license and about 100 calls a month; paid tiers cost money
  and reviewers couldn't reproduce our numbers without their own subscription.
- Because: the brief asks for public data, and every number must be reproducible from the committed
  snapshot or a free source.
- Known limit: OpenSky's terms restrict commercial use, and an investment firm is commercial. Stated
  in the design doc; a paid feed with a commercial license is the production upgrade.
- Revisit if: the work moves from a demo to real client use.

## D7: What the score measures (signals)
- Chose: two scored dimensions. **Strain**: airspace (NAS) delay minutes per landed flight and the
  cancellation rate (BTS On-Time, diverted flights excluded), and the fare premium versus markets of
  similar distance (DOT Table 1a). **Growth**: passengers per day versus the same quarter of 2019
  (DOT Table 1a). Friction (D10) is subtracted.
- Over: carrier concentration in the score (one dominant airline can mean captive demand or a risk,
  so its direction can't be defended; it is shown in answers, not scored); raw passenger volume
  (size is not promise; it feeds confidence instead, D12); delay alone (it can't tell LAX from SNA,
  both about 2.2 min).
- Because: "demand is outgrowing capacity" needs both a sign of overload today and a sign demand is
  rising, and these are the measured signals the free sources give us.
- Revisit if: a free source gives gate or terminal capacity, which would measure strain directly.

## D8: Combine signals as a weighted sum of percentile ranks
- Chose: each signal becomes a 0–100 percentile rank across the airports in scope, then a weighted sum.
- Over: z-scores (keep real distances, but one outlier such as EWR's 8% cancellations stretches the
  scale for everyone); a multiplicative score (one missing or zero signal wipes out the score).
- Because: robust to outliers and easy to say out loud ("SFO is in the 95th percentile for delay").
- Revisit if: analysts need to know how far apart two airports really are, not just their order.

## D9: Weights and presets, all in config/scoring.yaml
- Chose: Balanced = Strain 50 / Growth 50 (the default). Growth-focused = 30 / 70.
  Congestion-focused = 70 / 30. Inside Strain: delay 50, cancellations 25, fare premium 25.
- Over: one fixed set (can't answer "rank by growth instead"); equal thirds inside Strain (treats
  fare premium, an indirect signal, the same as measured delay).
- Because: equal weight is the easiest split to defend (both strain and growth are needed), and named
  presets let the agent switch views without new code. Weights live in YAML, so they can be changed
  live without Python.
- Revisit if: one preset turns out to drive every answer.

## D10: Friction is a sourced penalty from a curated file
- Chose: `data/constraints.yaml`, one entry per airport, each constraint with a source link and a
  penalty of 10 (minor, e.g. a curfew), 20 (major) or 30 (a hard cap) points off the 0–100 score.
  Only facts marked ✅ in `docs/DOMAIN_NOTES.md` qualify. No entry = no penalty, shown as "none on file".
- Over: no friction in the score (SNA would rank as if it could grow freely); penalties hard-coded in
  Python (same numbers, invisible to a reviewer).
- Because: it is a judgement input, so it must be visible, sourced and easy to change. The design doc
  says it is judgement.
- Open: how several constraints at one airport combine (sum or the largest), settled when the
  scoring is built.
- Revisit if: the file grows beyond what one person can check.

## D11: Scope: commercial airports in DOT Table 1a, lower 48
- Chose: rank airports with commercial service in DOT Table 1a in the lower 48. Alaska is answered
  only through OpenSky questions (no score). Out of scope: cargo economics, financing, airline
  strategy, construction cost; the agent says so and offers what it can do.
- Over: including Alaska and Hawaii (DOT has no Anchorage rows, so they'd rank with missing signals);
  only the top 50 hubs (drops New England airports Q1 asks about).
- Because: one consistent data source for every ranked airport keeps the ranks comparable. Small
  airports stay in, flagged by D12 rather than dropped.
- Revisit if: a source with Alaska and Hawaii fare data appears.

## D12: Confidence flag for thin data
- Chose: an airport is **Low confidence** if any scoring signal is missing or it has fewer than 10
  markets in the DOT table. The score is still shown, with the flag and the reason. The threshold
  is in `config/scoring.yaml`.
- Over: dropping thin airports (New England's small airports would vanish from Q1).
- Because: an analyst should see the airport and know how much to trust its number.
- Revisit if: most airports in a region end up flagged.

## D13: Anchorage long-haul share (OpenSky)
- Chose: count only flights by a fixed list of passenger-airline callsign prefixes; drop
  same-airport and short local hops; "long-haul" = over 1,500 miles great-circle distance (from
  OurAirports coordinates). Flights with no known destination (~14%) are reported separately, never
  guessed.
- Over: 3,000 miles (a tiny share that's hard to compare); counting every non-local flight (mixes
  cargo and private flights into a passenger question).
- Because: 1,500 miles is roughly Anchorage to Seattle and beyond, the natural line between in-state
  and long-haul flying. The filter uses only what the data shows.
- Revisit if: OpenSky's destination estimates prove unreliable on a second sample.

## D14: When a domain fact counts as verified
- Chose: a fact checked against a primary source, with corrections applied, is ✅ and may be stated
  as fact. The LAX 2025 passenger figure stays unconfirmed (⬜, "reportedly") until it's opened on
  LAWA's own page, because it was read through a search index.
- Over: keeping all corrected facts unverified (the SNA cap and SFO runway facts are central to two
  of the four example questions).
- Because: the check against the primary source is what makes a fact safe to state; needing a
  correction shows the check worked.
- Revisit if: a primary source changes (the SNA settlement runs only to the end of 2030).

## D15: No retrieval (RAG) layer
- Chose: no document index or vector database. Numbers come from tools over tables; the ten verified
  facts come from a small lookup by airport.
- Over: RAG (split documents into chunks, find similar ones, paste them into the prompt).
- Because: our data is structured numbers plus a short fact list. Retrieval would add a search step
  that can miss or blur passages, which works against "every number from a tool".
- Revisit if: analysts want to ask about large document sets, such as airport master plans or FAA
  reports.
