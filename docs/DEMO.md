# Demo script (about 10 minutes)

For the follow-up call. Run it on a laptop at `localhost`, or on the live site. Numbers below come
from the saved real answers in [docs/examples/flash/](examples/flash/README.md) (named per step);
numbers marked "computed" were produced by running the scoring on the current data snapshot.
Anything the model says live may be worded differently, so check the numbers on screen, not here.

## Setup (before the call)
1. Start it: `export GEMINI_API_KEY=...` then `docker compose up --build`, and open
   http://localhost:8000/. Or use the live site, https://airport-agent.fly.dev/ (it sleeps when
   idle: open it a few minutes early).
2. Have `config/scoring.yaml` open in an editor, and a terminal in the repo folder.
3. Check the page shows the five suggested questions and the "Rank, compare or profile directly
   (no model)" picker. The microphone button is there only with a key, on `localhost` or HTTPS.

## The run
Each step: type the question (or click the suggestion), show what is on screen, say the line.

1. **Type or click:** "Which New England airports are the best terminal-expansion candidates?"
   *See:* the tool step list, then a ranking table with Strain, Growth and Friction bars, and
   "How I got this" (open it). Transcript `a-new-england`: 7 ranked, BOS first at 48.2, BGR second
   at 46.0 marked Low confidence, HVN "not ranked: no measured delay data".
   *Say:* "Every number comes from a tool, never from the model's memory; the model explains."
2. **Type:** "And what about Hartford?" *See:* no new ranking; it answers from the same result,
   Hartford's airport is BDL (transcript `a-new-england`: score 32.0, 5th of 7 in the region,
   national 113 of 138). This exact follow-up is not in the saved transcripts, so it is expected.
   *Say:* "It remembers the conversation, and it knows Hartford means BDL."
3. **Click:** "How do LAX and SNA compare on congestion?" *See:* a comparison table; SNA with a
   friction penalty. Point at SNA's passenger cap: 30 points, a dated verified fact ("checked
   2026-10-11, review by 2030-12-31") with its source link. Transcript `b-lax-vs-sna`: LAX 21.9;
   SNA 30.5 before friction, 0.5 after, last of 138.
   *Say:* "SNA is not congested, but a legal cap on growth makes it a poor expansion bet, so the
   rules take points off, and show the source and the date."
4. **Click:** "What share of Anchorage's passenger departures are long-haul?" *See:* one number,
   59.9% (206 of 344 departures with a known destination), source OpenSky, 2026-10-04 to
   2026-10-10, and the stated limit: 74 departures had no destination and were not counted;
   destinations are estimated (transcript `c-anchorage-long-haul`).
   *Say:* "It gives the number with its limit instead of sounding certain."
5. **Click:** "Is there unmet demand at SFO, and why?" *See:* delay at the 100th percentile but
   growth -8.8% (transcript `d-sfo-unmet-demand`), the runway-spacing and Bay-fill notes with a
   source and a date, and a major friction penalty (20 points). Point out which sentences are
   measured, which are verified facts, and which are labelled inference or general knowledge.
   *Say:* "Delay is measured. The reason is a sourced fact. Anything beyond that is labelled."
6. **Type:** "Now do the same for the LA area." *See:* a new ranking for LA, not New England
   (transcript `h-trap-region-switch`: ONT first at 32.2, then BUR, LAX, LGB, SNA last at 0.5).
   *Say:* "'The same' meant ranking; it switched the region and kept the settings."
7. **Type (the trap):** "What's the ROI in dollars of expanding BOS's terminal?" *See:* no tool
   calls; it declines (financing, construction cost and dollar return are out of scope) and offers
   BOS's ranking, profile or demand signals instead (transcript `g-trap-roi-in-dollars`).
   *Say:* "It says what it can't do, and doesn't invent a figure."

## Live change (the owner edits the scoring)
1. In `config/scoring.yaml`, under `presets: balanced:`, change `strain: 50` to `strain: 100`.
   Save. Restart (Docker: `docker compose up`; locally: restart `uvicorn`). Re-ask question 1.
2. Expected (computed on the current snapshot by running the scoring on a copy of the file; the
   file in the repo was not touched): the weights move from delay 25 / cancellations 12.5 / fares
   12.5 / growth 50 to 33.3 / 16.7 / 16.7 / 33.3. BOS rises from 48.2 to 58.4, BTV (Burlington)
   overtakes BGR (Bangor) for second place (47.6 against 46.0), and BDL, PVD and PWM shuffle
   (BDL 39.6, PVD 37.8, PWM 37.0). BGR stays at 46.0: its growth is missing, so its weight moves
   onto its other signals.
   *Say:* "More weight on strain favours airports that are already congested, so Boston pulls
   ahead. No Python changed: the weights live in one file."
3. Then **undo it**: set `strain` back to `50`, and check with `git diff config/scoring.yaml`
   (it must print nothing).

## Voice (optional)
On `localhost` with a key and Chrome or Edge, hold the microphone button ("Hold to talk"), say
"How do LAX and SNA compare on congestion?", and release: the words are asked. If the button is
missing, skip this step; do not apologise for it.

## If something fails
- No key, or over the daily cap on the live site: the suggested questions and the picker still run
  the tools and show their results. Use those and say so.
- The model is slow: it runs at the "low" thinking level (`GEMINI_THINKING_LEVEL`, default `low`);
  answers in the saved run took 2 to 13 seconds. Fill the wait by opening "How I got this".
- The live site is asleep: reload after a few seconds.
