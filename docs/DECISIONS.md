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
- Chose: two scored dimensions. **Strain**: delay minutes per landed flight on flights into the
  airport from BTS's "National Aviation System" (NAS) cause (airport and airspace, as BTS defines
  it), the cancellation rate (diverted flights excluded), and the fare premium versus markets of
  similar distance (DOT Table 1a). **Growth**: passengers per day versus the same quarter of 2019
  (DOT Table 1a). Friction (D10) is subtracted.
- Time windows: Strain uses the latest 12 months of BTS data (now Aug 2025 to Jul 2026), so one odd
  month can't drive the ranking. Growth compares the latest DOT quarter with the same quarter of 2019.
- Fare premium: the airport's passenger-weighted average fare per mile, divided by the national
  average fare per mile for markets in the same distance band (0–500, 500–1,000, 1,000–1,500 and
  over 1,500 miles).
- Over: carrier concentration in the score (one dominant airline can mean captive demand or a risk,
  so its direction can't be defended; it is shown in answers, not scored); raw passenger volume
  (size is not promise); delay alone (it can't tell LAX from SNA: 2.3 vs 2.2 min in July 2026).
- Because: "demand is outgrowing capacity" needs both a sign of overload today and a sign demand is
  rising, and these are the measured signals the free sources give us.
- Revisit if: a free source gives gate or terminal capacity, which would measure strain directly.

## D8: Combine signals as a weighted sum of percentile ranks
- Chose: each signal becomes a 0–100 percentile rank across every airport in scope (D11), including
  Low-confidence ones; ties share the average rank. The ranks are combined as a weighted sum.
- Missing signal: its weight is spread over the airport's other signals in proportion to their
  weights, and the airport is flagged Low confidence with the missing signal named (D12).
- Over: z-scores (keep real distances, but one outlier such as EWR's 8% cancellations stretches the
  scale for everyone); a multiplicative score (one missing or zero signal wipes out the score);
  scoring a missing signal as 0 (a data gap would look like a real weakness).
- Because: robust to outliers and easy to say out loud ("SFO is in the 95th percentile for delay").
- Revisit if: analysts need to know how far apart two airports really are, not just their order.

## D9: Weights and presets, all in config/scoring.yaml
- Chose: Balanced = Strain 50 / Growth 50 (the default). Growth-focused = 30 / 70.
  Congestion-focused = 70 / 30. Inside Strain: delay 50, cancellations 25, fare premium 25. Presets
  change only the Strain/Growth split; the mix inside Strain stays the same. So under Balanced,
  delay counts 25% of the score, cancellations 12.5% and fare premium 12.5%.
- Over: one fixed set (can't answer "rank by growth instead"); equal thirds inside Strain (treats
  fare premium, an indirect signal, the same as measured delay).
- Because: equal weight is the easiest split to defend (both strain and growth are needed), and named
  presets let the agent switch views without new code. Weights live in YAML, so they can be changed
  live without Python.
- Revisit if: one preset turns out to drive every answer.

## D10: Friction is a sourced penalty from a curated file
- Chose: `data/constraints.yaml`, one entry per airport, each constraint with a source link and a
  tier: minor (10 points, e.g. a curfew), major (20) or hard cap (30), taken off the 0–100 score.
  The owner assigns each tier. If an airport has several constraints, only the largest penalty
  counts, because constraints overlap (SNA: passenger cap 30 and curfew 10, so 30). The score never
  goes below 0. Only facts marked ✅ in `docs/DOMAIN_NOTES.md` qualify. No entry means no penalty,
  shown as "none on file".
- Over: no friction in the score (SNA would rank as if it could grow freely); adding penalties
  together (overlapping limits count twice); penalties hard-coded in Python (same numbers, invisible
  to a reviewer).
- Because: it is a judgement input, so it must be visible, sourced and easy to change. The design doc
  says it is judgement.
- Revisit if: penalties of 30 move airports more than the signals do. Percentile scores cluster near
  the middle, so check the spread once real scores exist.

## D11: Scope: commercial airports in DOT Table 1a, lower 48
- Chose: rank airports with commercial service in DOT Table 1a in the lower 48. Alaska and Hawaii are
  not ranked; Anchorage is answered only through OpenSky questions (D13). Out of scope: cargo
  economics, financing, airline strategy, construction cost; the agent says so and offers what it can
  do.
- Over: including Alaska (DOT Table 1a has no Anchorage rows, so it would rank with missing signals);
  only the top 50 hubs (drops the New England airports Q1 asks about).
- Because: the same data sources for every ranked airport keep the ranks comparable. Small airports
  stay in, flagged by D12 rather than dropped.
- Revisit if: the analysts ask about Hawaii, or a source with Alaska fare data appears.

## D12: Confidence flag for thin data
- Chose: an airport is **Low confidence** if any scoring signal is missing, or if it has fewer than
  10 markets (distinct airport pairs in DOT Table 1a for the latest quarter). The score is still
  shown, with the flag and the reason. The threshold is in `config/scoring.yaml`.
- Over: dropping thin airports (New England's small airports would vanish from Q1).
- Because: Table 1a lists only the busiest markets, so few listed markets means the fare and growth
  numbers rest on a small part of the airport's traffic. An analyst should see the airport and know
  how much to trust its number.
- Revisit if: most airports in a region end up flagged.

## D13: Anchorage long-haul share (OpenSky)
- Chose: share = long-haul departures ÷ departures with a known destination, counting only
  passenger airlines (a fixed list of callsign prefixes). Same-airport flights and destinations under
  100 miles are dropped. "Long-haul" = over 1,400 miles great-circle distance (from OurAirports
  coordinates). Flights with no known destination (~14% in the sample) are reported separately with
  their count, never guessed.
- Over: 1,500 miles (would leave out Seattle, about 1,445 miles away and the main route to the lower
  48); "destination outside Alaska" (that's leaving the state, not distance); counting every flight
  (mixes cargo and private flights into a passenger question).
- Because: 1,400 miles sits just below Seattle. Every flight to the lower 48, Hawaii or Asia counts;
  every in-state flight (Fairbanks about 260 miles, Juneau about 570) and nearby Canada does not.
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
- Chose: no document index or vector database. Numbers come from tools over tables; the verified
  domain facts (nine of ten today) come from a small lookup tool, by airport or by topic (such as
  the PFC cap or how old BTS data is).
- Over: RAG (split documents into chunks, find similar ones, paste them into the prompt).
- Because: our data is structured numbers plus a short fact list. Retrieval would add a search step
  that can miss or blur passages, which works against "every number from a tool".
- Revisit if: analysts want to ask about large document sets, such as airport master plans or FAA
  reports.
