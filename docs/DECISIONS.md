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

## D2: Model tool use, no agent framework
- Chose: the model SDK's own tool use (function calling). The model routes and explains; code computes.
- Over: LangChain/LangGraph (heavy abstraction over ~50 lines), text-to-SQL (unchecked numbers), no
  model (fails conversational follow-up).
- Because: it gives the clearest line between AI and deterministic logic, which the brief asks us to
  explain.
- Revisit if: we need multi-step planning across many tools.
- Confirmed by the owner at Step 5: the loop is about 50 lines in `llm.py` on Google's SDK.

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
- Chose: Python 3.13, pinned in `pyproject.toml` (`==3.13.*`) and `.python-version`; uv reads it and installs
  that version locally and in CI, the Dockerfile will use the matching slim image.
- Over: 3.14 (newest, but some libraries and slim images lag), 3.12 (older,
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

## D6: AI agents write the code; I review every step
- Chose: AI agents write each step's code on a branch with a pull request. An independent AI
  reviewer checks every PR; each finding is fixed or declined with a reason. I then go through the
  step with the AI assistant (walkthrough, code tour) and merge. At the scoring step only, I also make a small change myself
  (a weight, a rule or a new signal).
- Over: typing the code myself, or writing it line by line with the AI (more of my time
  on mechanics, for the same understanding the walkthrough gives).
- Because: the brief grades reasoning and design. My time goes into the decisions (scope, KPI,
  weights), checking the work, and being able to explain and change every part.
- Unchanged: I decide scope, KPI and weights; weights live in `config/scoring.yaml` so I can change
  them live; I write `docs/DESIGN.md` and "How I work with AI" myself.
- Revisit if: a walkthrough shows I can't explain or change a part; then that part is rebuilt
  in smaller pieces with me checking each.

## D7: What the score measures (signals)
- Chose: two scored dimensions. **Strain**: NAS delay per landed flight, meaning BTS's `NASDelay`
  minutes (delay BTS attributes to the "National Aviation System": airport and airspace) on flights
  arriving at the airport, divided by flights that landed there; the cancellation rate (diverted
  flights excluded), and the fare premium versus markets of similar distance (DOT Table 1a).
  **Growth**: passengers per day versus the same quarter of 2019 (DOT Table 1a). Friction (D10) is
  subtracted.
- Time windows: Strain uses the latest 12 months of BTS data (now Aug 2025 to Jul 2026), so one odd
  month can't drive the ranking. Growth compares the latest DOT quarter with the same quarter of
  2019.
- Fare premium (latest DOT quarter): for each of the airport's markets, its fare per mile divided by
  the passenger-weighted national average fare per mile for markets in the same distance band
  (0–500, 500–1,000, 1,000–1,500 and over 1,500 miles); then the passenger-weighted average of those
  ratios across the airport's markets. 1.0 means fares are normal for those distances; 1.2 means 20%
  above.
- Growth: percent change in the airport's total passengers per day (summed over all its Table 1a
  markets in each period, whichever pairs are listed) between the latest quarter and the same
  quarter of 2019. Percent, not absolute, so small and large airports compare fairly.
- Over: carrier concentration in the score (one dominant airline can mean captive demand or a risk,
  so its direction can't be defended; it is shown in answers, not scored); raw passenger volume
  (size is not promise); delay alone (it can't tell LAX from SNA: 2.3 vs 2.2 min in July 2026).
- Because: "demand is outgrowing capacity" needs both a sign of overload today and a sign demand is
  rising, and these are the measured signals the free sources give us.
- Revisit if: a free source gives gate or terminal capacity, which would measure strain directly.

## D8: Combine signals as a weighted sum of percentile ranks
- Chose: each signal becomes a 0–100 percentile rank across every ranked airport (D11, D20), including
  Low-confidence ones: rank ÷ number of airports that have that signal × 100, so the top airport
  scores 100; ties share the average rank. For cancellations, delay, fare premium and growth,
  higher means more promising. The ranks are combined as a weighted sum.
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
- Because: equal weight is the easiest split to defend (both strain and growth are needed), and
  named presets let the agent switch views without new code. Weights live in YAML, so they can be
  changed live without Python.
- Revisit if: one preset turns out to drive every answer.

## D10: Friction is a sourced penalty from a curated file
- Chose: `data/constraints.yaml`, one entry per airport, each constraint with a source link and a
  tier: minor (10 points, e.g. a curfew), major (20) or hard cap (30), taken off the 0–100 score.
  The owner assigns each tier. If an airport has several constraints, only the largest penalty
  counts, because constraints overlap (SNA: passenger cap 30 and curfew 10, so 30). SFO: runway
  spacing and Bay fill, major (20), set by the owner at Step 4. The score never goes below 0. Only facts marked ✅ in `docs/DOMAIN_NOTES.md` qualify. No entry means no penalty,
  shown as "none on file".
- Over: no friction in the score (SNA would rank as if it could grow freely); adding penalties
  together (overlapping limits count twice); penalties hard-coded in Python (same numbers, invisible
  to a reviewer).
- Because: it is a judgement input, so it must be visible, sourced and easy to change. The design
  doc says it is judgement.
- Revisit if: penalties of 30 move airports more than the signals do. Percentile scores cluster near
  the middle, so check the spread once real scores exist.

## D11: Scope: commercial airports in DOT Table 1a, lower 48
- Chose: rank airports with commercial service in DOT Table 1a in the lower 48. Alaska and Hawaii
  are not ranked; Anchorage is answered only through OpenSky questions (D13). Out of scope: cargo
  economics, financing, airline strategy, construction cost; the agent says so and offers what it
  can do.
- Over: including Alaska (DOT Table 1a has no Anchorage rows, so it would rank with missing
  signals); only the top 50 hubs (drops the New England airports the first example question asks
  about).
- Because: the same data sources for every ranked airport keep the ranks comparable. Small airports
  stay in, flagged by D12 rather than dropped.
- Revisit if: the analysts ask about Hawaii, or a source with Alaska fare data appears.

## D12: Confidence flag for thin data
- Chose: an airport is **Low confidence** if any scoring signal is missing, or if it has fewer than
  10 markets (distinct airport pairs in DOT Table 1a for the latest quarter). The score is still
  shown, with the flag and the reason. The threshold is in `config/scoring.yaml`.
- Over: dropping thin airports (New England's small airports would vanish from the New England
  question).
- Because: Table 1a lists only the busiest markets, so few listed markets means the fare and growth
  numbers rest on a small part of the airport's traffic. An analyst should see the airport and know
  how much to trust its number.
- Revisit if: most airports in a region end up flagged.

## D13: Anchorage long-haul share (OpenSky)
- Chose: share = long-haul departures ÷ departures with a known destination, counting only passenger
  airlines (a fixed list of callsign prefixes, kept in configuration and set when the data layer is
  built). Same-airport flights and destinations 100 miles or closer are dropped. "Long-haul" = over
  1,400 miles great-circle distance (from OurAirports coordinates). Flights with no known
  destination (~14% in the sample) are reported separately with their count, never guessed.
- Over: 1,500 miles (would leave out Seattle, about 1,445 miles away and the main route to the lower
  48); "destination outside Alaska" (that's leaving the state, not distance); counting every flight
  (mixes cargo and private flights into a passenger question).
- Because: 1,400 miles sits just below Seattle, so the main routes to the lower 48, Hawaii and Asia
  count (a few small airports in northwest Washington fall just under the line);
  every in-state flight (Fairbanks about 260 miles, Juneau about 570) and Whitehorse or Vancouver
  do not.
- Revisit if: OpenSky's destination estimates prove unreliable on a second sample.

## D14: When a domain fact counts as verified
- Chose: a fact checked against a primary source, with corrections applied, is ✅ and may be stated
  as fact. The LAX 2025 passenger figure stays unconfirmed (⬜, "reportedly") until it's opened on
  LAWA's own page, because it was read through a search index.
- Over: keeping all corrected facts unverified (the SNA cap and SFO runway facts are central to two
  of the brief's four example questions: LAX vs SNA, and unmet demand at SFO).
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

## D16: The data layer computes the measured values; scoring only ranks them
- Chose: the data layer returns finished per-airport values (NAS delay per landed flight,
  cancellation rate, fare premium, growth vs the same quarter of 2019, market count), each with its
  source and as-of date. Scoring (Step 4) turns them into percentile ranks and applies the weights.
- Over: the data layer returns raw rows and scoring computes everything (one much larger scoring
  step, harder to explain and to change live).
- Because: each value is a measurement with its own source and date, so it belongs with the data;
  scoring stays small and pure.
- Revisit if: a signal needs data from more than one source at once.

## D17: A small dated snapshot is committed; raw downloads are not
- Chose: raw downloads stay in `data/cache/` (not in git). Small per-airport summaries are
  committed as dated snapshots by the `refresh` command, so a fresh checkout and the
  Docker image give the same answers without downloading anything.
- Over: cache only (every new machine must download several hundred MB first, and numbers can
  change between runs).
- Because: answers must not drift during a demo, and the data date should be visible in git.
- Revisit if: a snapshot grows past the size budget.

## D18: Passenger airline list for the Anchorage long-haul share
- Chose: callsign prefixes ASA, QXE, DAL, UAL, AAL, SCX, RVF, CFG, ICE, in `config/sources.yaml`
  (confirmed by the owner at Step 4).
  Left out: CPA, CAL, EVA, KAL, whose Anchorage flights are mostly cargo stops; a callsign alone
  can't tell their cargo flights from passenger ones.
- Over: counting every airline (mixes cargo into a passenger question).
- Because: D13 counts passenger airlines only.
- Revisit if: one of the left-out airlines starts scheduled passenger service through Anchorage.

## D19: Airport codes the sources disagree on, and missing months
- Chose: when DOT or BTS uses a code that OurAirports no longer lists as the airport's code (West
  Palm Beach: PBI in DOT and BTS, DJT in OurAirports), match it through an exact entry in
  OurAirports' keywords for a US airport with scheduled service, and show a note saying so. A code
  that still can't be matched (today only US territories such as SJU and GUM) is listed with its
  reason in the build's manifest, never dropped silently. If a month in the 12-month BTS window
  can't be downloaded, it is recorded as a gap and named in the delay and cancellation notes
  ("11 of 12 months; missing: Jan 2026"); it is never filled in.
- Over: a hand-kept alias list (needs upkeep and hides the source of the match); dropping unmatched
  airports (PBI vanished from the ranking); stopping the whole build for one missing month.
- Because: every airport in DOT Table 1a must be ranked or explained (D11), and a gap shown is
  better than a number quietly based on less data.
- Revisit if: a keyword match ever picks the wrong airport.

## D20: Only airports with measured delay data are ranked
- Chose: an airport needs the signals listed in `required_signals` in `config/scoring.yaml` to be
  ranked; today that is NAS delay only. Airports without it are listed as "not ranked" with the
  reason and left out of the percentile population, so they don't move anyone else's ranks. D8's
  weight spreading still covers other gaps (BGR has no growth signal: ranked, Low confidence).
- Over: requiring delay and growth (stricter; also unranks BGR and MDT); counting a missing signal
  as the 50th percentile (a gap would look average instead of absent); keeping D8 unchanged (on
  real data, 9 small fields with only a fare premium took ranks 1 to 7, because that one signal
  carried their whole score).
- Because: fare premium alone is an indirect sign (D7, D9); without measured delay there is no
  basis to judge strain.
- Revisit if: airports missing growth keep ranking near the top (MDT is #2 with no growth signal and
  2 markets); adding `growth_vs_2019` to the list is a one-line change.

## D21: Snapshots use only data published by their date
- Chose: `refresh --as-of YYYY-MM` keeps only data that was public by the end of that month.
  BTS on-time: a month counts once it ended at least 91 days earlier (BTS posts each month 6 to 13
  weeks after it ends; January 2026 appeared 90 days after month end). DOT Table 1a: a quarter
  counts 6 whole months after it ends; this is an assumption (2026 Q1 appeared about 5 months after
  quarter end, and 2026 Q2 was still missing on 2026-10-11). BTS boardings: years up to the year
  before. OurAirports: today's file in every snapshot, since it keeps no history; the manifest
  says so. OpenSky: latest snapshot only; older ones show long-haul as "not available for this
  date". In the 2019 snapshot, growth vs 2019 is empty with the reason "this snapshot is the 2019
  baseline". Three snapshots are committed: 2019-12, 2021-12 and the latest. "Latest" means the newest plain refresh: only versions named `latest-YYYY-MM-DD[-N]` count, and point-in-time snapshots (`2019-12`, `2021-12`, any `--as-of`) are fetched only by name.
- Over: using whatever the API returns today for an old date (a 2019 snapshot would quietly use
  data nobody had in 2019); a fixed 3-month BTS lag (a snapshot dated end of April 2026 would
  include January 2026, which appeared on 1 May).
- Because: comparing snapshots must show what an analyst could actually have known at the time.
- Revisit if: DOT's release dates are found published, so the 6-month assumption can be checked.

## D22: The agent's defaults
- Chose: a Flash-tier Gemini model (`GEMINI_MODEL`) with thinking level low (about 11 s per answer
  instead of about 44 s at the default level); a 120 s request timeout; at most a set number of tool
  calls per question; a national ranking with no region shows the top 10; the Anchorage long-haul
  share only at the configured 1,400 miles (the stored summary keeps counts, not distances). A
  spent quota fails at once with Google's message instead of waiting hours. All are environment
  variables.
- Over: the model's default thinking level (four times slower for the same tool choices on the
  questions tried); a Pro-tier model by default (Step 7 compares it on the four questions, D3).
- Because: answers must come back fast enough for a live demo, and every limit is visible and
  changeable without code.
- Revisit if: Step 7 shows the Pro tier answers the four questions clearly better.

## D23: Every verified fact and penalty is dated, and stale ones are flagged
- Chose: each verified fact in `docs/DOMAIN_NOTES.md` and each penalty in `data/constraints.yaml`
  carries `checked` (when it was verified) and `review_by` (when it must be re-checked). Rules and
  agreements are due on their known end date (the SNA passenger cap and curfew: 31 Dec 2030, when
  the settlement agreement ends; the curfew itself runs to 2035, and the sooner date is used);
  physical facts and statistics one year after checking. A penalty is due when its earliest note
  is. After `review_by` the agent says the fact may be out of date and the tables mark the penalty
  "stale"; the penalty still applies.
- Over: undated facts (an answer could state a years-old rule as current); dropping a penalty once
  stale (one missed re-check would silently change the ranking); watching the sources
  automatically now (a separate, later step).
- Because: a verified fact is a snapshot of the day it was checked, like the data; old facts must
  be visibly old.
- Revisit if: a rule changes before its review date, or the source watch is built.

## D24: How the web chat behaves
- Chose: a one-page chat with no framework or build step, streaming each tool step and the answer as
  server-sent events; the server keeps no conversation state. Follow-up questions send earlier turns
  as text only, so the tools run again rather than reusing old results. For a typed question with a
  model key, a tool that returns an error shows as a failed step and the model still answers. The
  rank / compare / profile picker, and the suggested questions when there is no key, run the tools
  directly: a tool error ends that run with its message. A crash ends the answer with an error
  message. A data source is marked stale (amber) when its data ends more than 18 months before
  today, or before the snapshot's own date for older snapshots (`freshness.stale_after_months` in
  `config/sources.yaml`). The over-time question picks its two versions itself and ignores the
  version picker. The picker also works when a key is set, and its results stay out of the chat
  history.
- Over: reusing earlier tool results in follow-ups (a follow-up could quote numbers from another
  data version); a framework with a build step (more to install and explain for one page);
  keeping conversations on the server (state to store and clean up).
- Because: every number on screen must come from a tool run for that question, and the page must
  stay simple enough to change live.
- Revisit if: follow-ups get slow or costly because the tools run again.

## D25: Keep the Flash-tier model
- Chose: `gemini-3.8-flash` at thinking level low, after running the four questions and five trap
  questions on Flash and Pro (`docs/examples/`; Pro run 2026-10-11, Flash re-run 2026-10-12
  after this step's tool and prompt fixes).
- Over: the Pro tier (`gemini-3.1-pro-preview`): about 3x the cost per question ($0.0170 against
  $0.0057, with the token counts the API reports; Flash is $0.0079 estimated with tool results,
  which the Pro run did not measure), slower (108.3 s against 63.4 s for the ten questions), and its errors were reasoning errors: it misread a tool error (said SJU is
  missing from the BTS data, which the error said holds it), treated a friction penalty as the
  reason SFO's runways were never moved, and claimed a "national average" the tools don't give.
  Flash's errors came mostly from tool wording (the count of ranked airports read as a rank,
  "61.2th percentile"), fixed in this step, plus one "below the national average", now ruled out
  in the prompt.
- Because: equal number accuracy (every number in every answer was found in the tool results, for
  both) at a third of the cost.
- Revisit if: a re-run shows Flash misreading tool results the fixes should have prevented.

## D26: A public Fly site with a daily cap on model questions
- Chose: a public site on Fly (`airport-agent.fly.dev`) for about two days around the hand-in,
  open to anyone with no sign-in, with a daily cap on questions sent to the model
  (`MAX_MODEL_QUESTIONS_PER_DAY`, 300 per UTC day, counted in memory). Over the cap, free-form
  questions get a message; the suggested questions and the picker still run the tools. The
  deploy runs one machine (`--ha=false`), so the cap is 300 in total, not per machine; the count
  starts again whenever the machine stops when idle or restarts, so it bounds a runaway client
  rather than being an exact daily total. Each request is size-limited too (a 2,000-character
  question, at most 10 earlier turns and 20,000 characters of history), so one question can't be
  made huge.
- Over: localhost only (reviewers can't try it live); an access code (friction for reviewers, for
  a short exposure); no cap (one runaway client could run up model costs).
- Because: reviewers can try the agent themselves with nothing to set up, and the cost of a
  two-day exposure stays bounded (the Gemini key's own spending cap is the last guard).
- Revisit if: the site stays up longer or the cap is hit.

## D27: Bad-weather runway capacity as a committed reference table, shown only
- Chose: Table 1 of the FAA's "Airport Capacity Profiles" (2014), typed into
  `data/faa_capacity_profiles.yaml` and read directly (like `data/constraints.yaml`), giving a
  shown-only signal `bad_weather_capacity_loss`: 1 minus the instrument-weather midpoint over the
  visual-weather midpoint, for 30 airports. It carries as-of "2014" and a note that it is runway
  capacity, not terminal space. It is not in the scoring and not in the snapshots.
- Over: the newest per-airport profiles (2015 to 2019: mixed dates, and the numbers sit in
  charts); scoring it (30 of about 138 airports would have it, so most would get no value);
  putting it in the snapshots (a rebuild would refetch every source and change today's numbers).
- Because: one dated table with numbers in text is the cheapest source we can check against the
  report, and showing it adds a bad-weather angle without moving any rank.
- Revisit if: the FAA publishes a newer summary table, or its coverage grows enough to score.
- Decided by the owner on 2026-10-12 (source and shown-only).

## D28: Watch fact sources with a fingerprint; a person re-verifies
- Chose: `airport-agent check-facts` downloads the source of every verified fact, strips the text of
  `script` and `style`, dates right after a "last updated / modified / reviewed" label, and
  copyright years (nothing else: a missed change costs more than a false alarm), and compares a sha256 fingerprint of the text with the one stored in
  `data/fact_fingerprints.json`. A changed or vanished source is reported, and with a token one
  GitHub issue names the facts and quotes old against new (a later run comments on the open one).
  A page that changes by design is listed as "not watched". Blocked or slow sources are
  "unreachable", never an alarm. The program never edits a fact. It also runs after a refresh
  with `refresh --check-facts`, a flag so the monthly build does not need the network twice by default.
- Over: updating facts automatically (a model or script rewriting a verified claim breaks the
  rule that a person verifies); no watch (a fact's "checked" date would quietly go out of date
  when its source moves).
- Because: dates say how old a fact is; the watch says when to look again, cheaply and with the
  standard library only.
- Limits: listing pages (FAA PFC, Alaska press releases, SNA reports) may alarm when an item is
  added, and a person closes it; comparing each fact's quoted wording is a possible follow-up;
  it sees that text changed, not whether it matters; it does not see news reported
  elsewhere before the page changes; PDFs are compared by bytes, so a re-saved file alarms;
  the baseline is the day it was recorded, not the day each fact was checked.
- Revisit if: false alarms swamp real ones, or a source needs a smarter comparison.

## D29: Talk mode: the server relays the audio
- Chose: the browser streams microphone audio over a WebSocket to our server (`/talk`), and the
  server holds the Gemini Live API session and relays both ways: microphone audio up, the model's
  speech and the tool results down. Tools run on the server through the same code as typed
  questions, so the page draws the same tables. Switched off unless `TALK_MODE=on`; each session
  counts as one question for the daily cap, lasts at most 5 minutes, ends after a minute of
  silence, and is accepted only from pages served by the same host.
- Over: the browser talking to Gemini directly with a short-lived token (less latency and less
  load on our server, but tool calls would arrive in the browser, which would have to send them
  back to the server to run, and the daily cap could not see the conversation); a browser
  speech-to-text and text-to-speech loop around typed chat (no new API, but slow turn-taking and
  no interruptions).
- Because: the key never leaves the server, tools and the cap stay where they already are, and
  one WebSocket needs no new dependency (the web server already handles them).
- Revisit if: the extra hop's latency is noticeable, or the site gets enough Talk sessions to
  load the server.
- Decided by the owner on 2026-10-12 (relay, not a browser token).

## D30: Scoring checked against outside research; hard cap and Strain mix kept
- Chose: keep the hard cap as a 30-point penalty (SNA still ranks, marked down with its reason),
  and keep Strain's mix at delay 50 / cancellations 25 / fares 25.
- Over: taking hard-capped airports out of the ranking (hides a case an analyst wants to see and
  discuss); lowering delay's share (the outside research notes delay reflects airspace and runways
  as much as terminal space).
- Because: both are numbers in `config/scoring.yaml`, so an analyst who weighs them differently can
  change them live, and `docs/DESIGN.md` already states the limit of delay as a terminal signal.
- Also checked (#72): the FAA Terminal Area Forecast has a yearly spreadsheet download after all
  (`taf.faa.gov/Downloads`), so it is the first candidate for a forecast signal; TSA checkpoint
  counts per airport appear to exist only as weekly PDFs from about 2020 (from search results, not
  confirmed on the primary page), so they are not adopted; a backtest against announced terminal
  projects needs each project's date and cost checked first. `docs/DESIGN.md` still says the
  forecast has no bulk download; the owner writes that file and will correct it.
- Revisit if: an analyst's use shows capped airports should be hidden, or a backtest shows another
  Strain mix ranks past expansions better.
- Decided by the owner on 2026-10-12.

## D31: Data releases separate from code releases
- Chose: a `Refresh data` workflow (weekly or by hand) builds the snapshot on GitHub's machine and
  publishes it as a GitHub release `data-YYYY-MM-DD`; every running server downloads the newest
  one at startup, in the background, with no token, and keeps the snapshot baked into its image
  when GitHub can't be reached or the archive fails the snapshot checks. A Data panel shows who
  built the data in use; refreshing on the server itself (`ALLOW_LOCAL_REFRESH=true`) and starting
  the workflow from the page (`GITHUB_TOKEN_REFRESH`) are off unless a maintainer switches them on.
- Over: new data through a pull request and a new image (fully reviewed, but every data update is
  a redeploy); refreshing only inside the app's container (needs a few hundred MB of memory, and
  anyone with the page could start heavy work); a worker and a queue (right at scale, too much
  here); publishing straight into an object store (one more account and credential).
- Because: new data reaches every copy without a rebuild, bad data rolls back by deleting its
  release (on Fly, where a restart throws installed files away, servers load the previous one
  when they next start; where installed files are kept, also delete the installed `latest-…`
  folder from the data store, or set `DATA_RELEASES=off` to stop downloads), the app stays small and keeps
  working when GitHub is down, and the only write permission is the workflow's own, on its
  publishing job.
- Revisit if: published data needs a person's review first (the workflow would open a pull request
  and wait), or the snapshots outgrow release files.

## D32: A daily limit per visitor on model questions
- Chose: a second limit, `MAX_MODEL_QUESTIONS_PER_VISITOR_PER_DAY` (20 on Fly, unset elsewhere
  means none), counted per visitor in memory and reset at the UTC day change. The visitor is the
  `Fly-Client-IP` header when present, else the client address. It applies to typed questions and
  to Talk mode, and over it the behaviour is the same as over the site-wide cap, with its own message.
- Over: only the site-wide cap (one visitor could use up all 300 questions and lock everyone else
  out); a sign-in or access code (friction for reviewers); a shared store for the counts (one more
  service, for a single machine).
- Because: one visitor can't drain the site-wide cap. Known limits: visitors behind a shared
  address (an office) count as one; a restart resets the counts; the header is trusted only because
  Fly's proxy sets it, so anywhere else a client could send its own.
- Revisit if: the site runs on more than one machine, or real visitors hit 20.

## D33: A production deploy waits for the example questions
- Chose: before a deploy from `prod`, the Deploy workflow runs `scripts/evaluate.py --check`: the
  nine example conversations against the live model, and all nine must pass. A conversation
  passes when every question gets an answer (no error, no stop at the tool-call limit, not
  empty) and the number check finds no number in any answer that no tool result gave. No model
  grades anything. It costs about $0.07 and about a minute per release. It is skipped when the
  workflow runs on a `v*` tag, because that is a rollback. A failure stops the job before anything
  is deployed; a flaky one is re-run by hand.
- Over: a lower bar such as 8 of 9 (the number check is exact, so a miss is a real finding); a
  model grading the answers (not deterministic, costs more); checking on every pull request
  (spends money on work that never ships); blocking rollbacks too (a bad day for the model
  would then stop the way back to a good release).
- Because: the rule that every number comes from a tool is then tested before users see a
  release, with the same key and model that production uses.
- Revisit if: it fails often for reasons that are not real regressions, or a question is added
  that cannot be judged by the number check alone.

## D34: Type checking with mypy, default strictness, source only
- Chose: `mypy` on `src/airport_agent` at its default strictness, run by `scripts/ci-local` and by
  CI after the lint step, with the `pandas-stubs` and `types-PyYAML` stub packages as dev
  dependencies. Tests are not type-checked. Function bodies are checked even without annotations
  (`check_untyped_defs`), because most of this code has none and mypy would otherwise skip it.
- Over: pyright (its pip package downloads Node.js on first run, and this project is pure Python);
  `--strict` (it would mean annotating every function for little gain at this size); no type
  checking (annotations would drift from what the code does).
- Because: it found real gaps cheaply (an unannotated empty set, a list of questions typed as
  `object`) and keeps the annotations honest as the code changes.
- Revisit if: the project grows enough that unannotated functions hide bugs (turn on `disallow_untyped_defs`),
  or mypy's speed or stubs become a drag.
