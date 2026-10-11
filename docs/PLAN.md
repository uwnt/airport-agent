# Plan: Airport Investment Intelligence Agent

**Hand-in deadline:** 2026-10-12, 09:45 UTC. Plan backwards from it.

This is the working plan for the take-home. Each step says **what** we do, **why**, **what else we could
have done and why we didn't**, and **what you own** in it. Check off steps as they land. Decisions made
along the way go in `docs/DECISIONS.md`, which feeds the design document at the end.

## The assignment in one paragraph
An investment firm wants an agent that helps analysts find US airports where a terminal renovation
would pay off, because demand is outgrowing capacity. It must pull **public aviation data**, **rank or
compare airports with deterministic logic** (not only language-model output), **explain its reasoning**,
handle **follow-up questions in a chat** (voice is a bonus), and be honest about **assumptions,
uncertainty and scope**. Deliverables: source code and a short design doc covering scoring methodology,
key tradeoffs, and where and how AI is used. It is graded on **clarity, reasoning and thoughtful design,
not completeness or polish**.

That last line is the most important sentence in the brief. It tells us to build a **narrow agent that
is obviously right about what it covers and openly says what it doesn't**, rather than a wide one that
bluffs.

## Ground rules we carry over from our project work
These habits come from running real projects, and each one shows up in the grade:

| Habit | Why it matters here |
|---|---|
| **Write the plan and the decisions down before coding** | The design doc is half the deliverable. If decisions are logged as we go, it writes itself. |
| **Least code**: standard library first, then what's already installed, then a small dependency | Reviewers read every line. Less code makes your reasoning easier to see. |
| **The deterministic core is pure and tested** | Scoring takes numbers in and gives numbers out, with no network and no model. That's how you prove it's "not only LLM output". |
| **Small commits, clear messages, one PR per step** | Your git history is the story of your thinking, and they will read it. |
| **An independent AI review on every PR**, posted as a readable comment, each finding fixed or declined with a reason | Shows you treat AI output as something to check, not to trust. This is your established workflow, shown on purpose. |
| **Secrets only in Doppler, never in git** | The repo goes public. One leaked key ends the conversation. |
| **Verify before saying done** | Run the four example questions for real before claiming they work. |
| **Say what you don't know** | It's a graded requirement here, not just politeness. |

## Architecture principles (decided up front; every step follows them)
1. **One image, two commands.** `refresh` is a batch job: it calls the public APIs, computes metrics
   and writes a dated snapshot to `data/snapshot/`. `serve` is the chat server and only reads the
   snapshot. In production, refresh is a scheduled job and serve scales independently.
2. **A server that keeps no state.** The browser sends the conversation history with each message, so
   any copy can answer and a restart loses nothing. (Redis is the alternative at scale; it's named in
   the design doc.)
3. **Configuration only from environment variables:** model, data folder, port, log level, cost
   limits. The same image runs everywhere. Secrets are never in the image.
4. **Every running copy says what it runs.** `/health` returns `{commit, snapshot_date, model}`.
5. **Cost and safety limits:** maximum answer tokens, maximum tool calls per question, and a request
   timeout, all configurable.
6. **Every number carries its source and "as of" date**, all the way to the answer text.
7. **AI is a layer, not the foundation: a no-key mode.** With no `GEMINI_API_KEY`, the app still
   works. The suggested questions and a simple rank / compare / profile picker call the tools
   directly and show the tables, bars and "How I got this" data, with fixed-wording summaries; only
   free-form chat is off. A reviewer can try it with no key, and it proves the analysis is
   deterministic.
8. **Point-in-time snapshots.** `refresh --as-of YYYY-MM` uses only data that existed by that date
   (the fare data reaches back to 1993, the delay data to 1987). Commit three small snapshots,
   **2019-Q4** (pre-pandemic), **2021-Q4** (recovery) and **latest**, and let the user pick a version.
   This shows on the call that updates change answers, using real history rather than fake data,
   and it enables a `compare_over_time` tool and later **backtesting** of the KPI. Limits to state:
   - OpenSky has no deep history on a free account, so old snapshots mark long-haul "not available
     for this date";
   - the friction file reflects current rules (dating them is a next step).
9. **Refresh is a container command; the scheduler and the data store are plug points.**
   - `airport-agent refresh` runs anywhere: GitHub Actions, GitLab, Bitbucket Pipelines, Jenkins, a
     Kubernetes CronJob, a cloud scheduler, or cron.
   - Data versions go to a store chosen by `DATA_STORE`, through a tiny interface (`latest()`,
     `get(version)`, `publish(snapshot)`):
     - `file://` (a local folder or network share): **built**, since it's needed for the baseline
       and local Docker;
     - `github://` (data releases): built only with stretch step 6d;
     - `s3://` (AWS, Google Cloud, Azure, and on-premises MinIO): **described in the design doc,
       not built** (untestable today).
   - **`serve` picks up new versions without a restart** (core, ~20 lines): it checks `latest()` at
     startup, every `DATA_CHECK_MINUTES` (default 5), and when "Get latest data" is clicked.
   - **Parse locally:** `docker compose run --rm refresh` writes to the shared `./data` folder
     (`DATA_STORE=file:///data`), and `serve` shows the new data within minutes. You can demo this
     live on the call.
   - **Parse on Fly:** a separate *scheduled* Fly machine runs the same image with `refresh` (more
     memory, runs for minutes) and writes to S3-compatible object storage (Tigris), because a Fly
     volume attaches to one machine only. `serve` uses `DATA_STORE=s3://…`. This is part of the
     later live-demo work; the simpler option of refreshing inside the chat machine with a volume is
     named as a tradeoff (memory contention, no scaling).
   - "The client wants data local" means `DATA_STORE=file://…` plus their own scheduler, with the
     same image. With no internet inside their network, the refresh runs outside and the snapshot
     comes in through their file-transfer process.

## Things that are easy to miss (checklist)
- [ ] One deterministic code lookup: IATA (DOT: `SFO`) ↔ ICAO (OpenSky: `KSFO`), from OurAirports.
- [ ] Ambiguous places: "LA" can mean LAX or the LA area (LAX, BUR, LGB, ONT, SNA). The agent states
      its reading or asks.
- [ ] Mixed data dates (fares to 2026 Q1, delays to 2026-07, boardings to 2023). Show each number's
      date, and use trailing four quarters to remove seasonality.
- [ ] **OpenSky's terms restrict commercial use.** An investment firm is commercial, so state this in
      the design doc and name a licensed alternative. DOT, BTS and OurAirports are public domain.
- [ ] A "How I got this" panel under each answer: the tools called, their inputs, the numbers they
      returned.
- [ ] A grounding test: every number in an answer appears in a tool result.
- [ ] A scope line in answers and the UI: decision support, not investment advice; what the score
      leaves out.
- [ ] One Python version, pinned in `pyproject.toml` and used in the Dockerfile. The server has 3.14,
      while slim images are usually 3.12 or 3.13, so pick one deliberately.
- [ ] A `Makefile`: `run`, `test`, `lint`, `refresh`, `docker`.
- [ ] **The image builds for both amd64 and arm64** (Docker buildx in CI). Many reviewers use
      Apple Silicon Macs.
- [ ] Commits use an email **verified on your GitHub account**, so every commit links to your
      profile. Use your real address (public) or your GitHub noreply address (hidden, same credit),
      your choice. Set it per repo at Step 0 (`git config user.email …`), and check the first pushed
      commit shows your avatar.
- [ ] Snapshots hold **processed per-airport numbers only** (estimate under ~1 MB each; measure in
      Step 3), never raw downloads.
      - **CI size budget:** fail if any snapshot is over 5 MB.
      - Only the three named snapshots are committed.
      - **Retention:** keep the last 10 data versions in a store, plus the named ones.
- [ ] **Cost per question** measured in Step 7, one line in the design doc.
- [ ] A license decision: none ("all rights reserved") or MIT, stated in the README.
- [ ] (Before starting) Ask the recruiter whether AI coding assistants are OK for the take-home.
- [ ] A Mermaid architecture diagram in `DESIGN.md` (GitHub renders it).
- [ ] A "Deploying it for real" paragraph:
      - the same image on Cloud Run, ECS or Fly;
      - refresh as a scheduled job;
      - platform secrets;
      - roll forward and roll back by image tag.

## Who does what
AI agents write the code; you decide, review every step, and must be able to **explain and change every part**.

| Part | Who writes | What you must be able to do |
|---|---|---|
| Scope, KPI, weights, out-of-scope list | **You decide**; Claude lays out the options | Defend every choice |
| Scoring (`scoring.py`, `config/scoring.yaml`, tests) | AI agents write; you get a file-by-file walkthrough, then make a small change yourself (a weight or a rule in `config/scoring.yaml`) | Explain every line; change a weight or rule live (weights are in YAML, no Python needed) |
| Agent instructions and tool descriptions (mostly plain English) | Claude drafts; you edit | Explain where AI is used and how it's kept honest |
| Data refresh, agent loop, server, chat page, Docker, CI | Claude writes; you get a code tour after each step | Say what each file does and how a question flows through it |
| `docs/DESIGN.md`, README "How I work with AI" | **You write**; Claude reviews | It's your reasoning in your words |

About 1,700–1,800 lines in total; the part you need to know deeply is about 250 (scoring plus the
agent instructions). After each step you get a file-by-file walkthrough and review it.

**On the call:** "I designed it and directed AI to write it. I reviewed every part, built the
scoring rules with it, and can change anything." That's true and credible.

## What the public data can actually answer (checked 2026-10-11)
Before planning features, we checked which free sources respond today. The 1-hour data spike in
Step 1 repeats this by hand, so you see it yourself.

| Source | What it gives | Access | Verified |
|---|---|---|---|
| **DOT Consumer Airfare Report, Table 1a** (`datahub.transportation.gov`, dataset `tfrh-tu9e`) | Every US airport-pair market per quarter, 1993–2026 Q1: passengers per day, average fare, distance in miles, the dominant carrier and its market share | Open API (Socrata), no key | ✅ 262k rows. **No Alaska rows** (0 for ANC) |
| **BTS enplanements, top 50 airports** (`data.bts.gov`, `2ydv-qfge`) | Yearly boarded passengers per airport, with coordinates | Open API, no key | ✅ up to 2023 only, top 50 only (most New England airports besides BOS are missing) |
| **FAA NAS Status** (`nasstatus.faa.gov/api/airport-status-information`) | Live delay programs and ground stops by airport | Open, XML, no key | ✅ answers; content is "right now" only |
| **OpenSky Network** (`opensky-network.org/api`) | Actual flights departing/arriving per airport (from transponder data) | Flight history **needs a free account** (anonymous got 403) | ⚠️ live positions work anonymously; history needs credentials |
| **OurAirports** (`davidmegginson.github.io/ourairports-data/airports.csv`) | Every airport: codes, type, state/region, coordinates | Open CSV download | ✅ 12.7 MB |
| **BTS On-Time Performance** (`transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_<YYYY>_<M>.zip`) | Every domestic flight: scheduled vs actual times, and delay minutes split by cause (**NAS** = airport/airspace, Carrier, Weather, Late Aircraft, Security) | Open monthly ZIP, no key | ✅ ~32 MB/month, latest 2026-07. A file download, not a query API: fetch a few months once, cache them |
| **FAA Terminal Area Forecast** (`taf.faa.gov`) | Official enplanement forecasts per airport | Web app; no data download found | ⚠️ PDFs and old summary tables only. Treat as a stretch goal; growth comes from DOT history instead |
| **FAA ASPM** (`aspm.faa.gov`) | Hourly airport efficiency, arrival rates | Login required | ❌ 503 and login-gated. Out of scope; name it in the design doc as the production upgrade |

Domain facts (caps, curfews, runway geometry, PFC rules) come from outside research and are listed with
their verification status in `docs/DOMAIN_NOTES.md`. The agent may only state a fact from that file
if it's marked verified with a primary source. Otherwise it labels the fact as unverified.

**What this means for the four example questions:**

1. *New England terminal-expansion candidates.* Airfare Table 1a covers BOS, BDL, PVD, MHT, PWM, BTV and
   others, so we can compute passenger volume, growth since 2019, and a fare premium (high fares for the
   distance flown suggest demand is outrunning supply) for each. **Answerable, and it's the core use case.**
2. *LAX vs Santa Ana (SNA) congestion.* Volume and growth come from Table 1a, live delays from NAS
   Status, and flights per hour from OpenSky. "Congestion" has no single public metric, so we define one
   and say so. SNA's curfew and passenger cap are real constraints, but they come from the model's
   general knowledge, not our data. **The agent must label them that way.**
3. *Long-haul share out of Anchorage.* ANC is **not** in Table 1a. We need OpenSky departures plus
   OurAirports coordinates to compute great-circle distance, and a stated threshold for "long haul".
   Two caveats to state: ANC is a major **cargo** hub, so transponder data mixes cargo and passenger
   flights unless we filter by airline; and OpenSky's airport assignment is an estimate. **Answerable,
   with stated uncertainty.** That makes it a good showcase question.
4. *Unmet demand at SFO, and why.* No dataset reports "unmet demand", so we infer it from signals:
   fare premium, passenger recovery versus 2019, and delay programs. The "why" (closely spaced runways,
   fog) is model knowledge, labelled as such. **Answerable as an inference, framed honestly.**

A missing data source is a scoping statement for the design doc, not a failure.

---

## What we hand in
Required: **source code** (the public repo) and **a short design doc** (`docs/DESIGN.md`). A hosted
website is not required. Aim for:
- a README quickstart that runs in ~5 minutes with **only `GEMINI_API_KEY`**;
- a **committed data snapshot** (small processed files with an "as of" date), so a reviewer needs no
  OpenSky account and gets the answers you got;
- **example transcripts** in `docs/examples/`;
- a **2–3 minute screen recording**: the four questions, one follow-up, voice;
- **three ways to run it**, all needing only `GEMINI_API_KEY`:
  1. a ready-made Docker image, `docker run -p 8000:8000 -e GEMINI_API_KEY=… ghcr.io/<you>/airport-agent:v1`;
  2. `docker compose up` after cloning;
  3. `uv run` for Python developers.

  This server has no Docker, so the image is built and smoke-tested **in GitHub Actions** on every PR,
  and published to GHCR at the `v1.0` tag.

**A reviewer without a Gemini key:**
- they use the **no-key mode** (architecture principle 7);
- for the call, optionally send them privately a **temporary, separate key** (its own Google Cloud
  project, restricted to the Gemini API, with a **daily request quota**, since budgets only alert),
  and delete it afterwards;
- never put a key in the image.

**Not in the 24 hours: a hosted live demo.** It comes after hand-in, before the call if time allows.
Design, so the design doc can describe it now:
- the same image on Fly.io, which serves the chat page and the API from one container;
- released by pushing a version tag (GitHub Actions deploys with a token limited to that one app);
- the machine stops when idle;
- a dedicated Gemini key with a spending cap, plus a passcode;
- data refresh: a scheduled Fly machine running `refresh` → Tigris (S3-compatible) →
  `serve` with `DATA_STORE=s3://…`, or GitHub data releases if Step 6d was built. Either way, data
  rolls back by pointing at the previous version.

The address and Fly organisation are decided then.

## Timeline (about 15 focused hours, plus sleep and buffer)

| # | Step | Time | Done when |
|---|---|---|---|
| 0 | Setup: GitHub repo, secrets, Python project, CI | 0:45 | `uv run pytest` passes on an empty test; CI is green |
| 1 | Data spike: call every source by hand | 1:00 | A sample of each saved under `data/samples/`; notes on what each can answer |
| 2 | Scope and KPI design (**your decisions**) | 1:00 | `docs/DECISIONS.md` has the KPI, weights, region rules and out-of-scope list |
| 3 | Data layer: clients plus local cache | 1:30 | Metrics for any airport come back from the cache with an "as of" date |
| 4 | Scoring engine, then a small change of your own | 2:00 | Pure functions, tests pass, a ranking for New England prints from the CLI |
| 5 | The agent: Gemini with tools, plus the no-key mode | 2:30 | The four example questions answered in a terminal chat, with follow-ups |
| 6 | Chat UI: streaming, ranking visuals, responsive (+ voice bonus) | 2:00 (+0:30) | Answers stream, tool steps show, rankings render as bars, and it works on a phone-width window; the mic works in Chrome |
| 6b | Docker: two-stage image, refresh + serve, compose, CI build and smoke test | 1:15 | CI builds the image, `/health` reports the commit; `docker compose up` works on your laptop |
| 6c | *Stretch:* "Talk" mode on Gemini's Live API | 3–5 h | Only after Steps 7–9 are safe; otherwise push-to-talk ships |
| 6d | *Stretch:* Data panel: refresh on **this machine** or **GitHub Actions**, "Get latest data", who built the data | 2:30–3:00 | After the graded steps are safe |
| 7 | Evaluate and harden | 1:00 | The four questions and a few traps run and are reviewed; caveats appear |
| 8 | Design doc and README (**you write**) | 1:30 | The three required sections plus a run guide |
| 9 | Hand-in | 0:45 | Snapshot committed, video recorded, public repo, secret and leak scans clean, link sent |

Front-load the risky parts (Steps 1 and 3) while you're fresh. Writing the docs is safer to do tired
than designing the scoring.

---

## Step 0 — Setup (0:45)
**What:**
- Create a private repo `airport-agent` on your personal GitHub.
- Create a fine-grained token limited to that one repo, and store it in Doppler as `GH_TOKEN`.
- Store `GEMINI_API_KEY` (a dedicated key with a spending cap) and the OpenSky credentials in Doppler.
- Run `uv init`, add ruff and pytest, and add one CI workflow.

**Why:** The repo, secrets and checks come first, because fixing them later means rewriting history.
The token is limited to one repo because this server's `gh` login belongs to a different account, and we must not
switch the whole machine to yours. Commands run as `doppler run -- gh …` use your token for that one
command only.

**Alternatives:**
- *Use the server's existing GitHub login.* Wrong account, and the commits would be tied to it.
- *Run `gh auth switch`.* That changes the login for every session on the box, including ops.
- *A `.env` file.* It's easy to commit by accident before a public push. Doppler keeps the value off
  disk entirely.
- *pip + venv instead of uv.* It works, but uv gives a lockfile (`uv.lock`) and one command for
  everything (`uv run …`). Reviewers can reproduce your setup exactly.
- *Poetry.* Also good, but slower and more ceremony than we need in a day.

**You own:** creating the repo, the token and the API keys (these need your accounts).
**Lesson:** a secret that never touches disk can't leak through git.

## Step 1 — Data spike (1:00)
**What:** Call each source in the table above by hand. Save a small sample of each response to
`data/samples/`. Write down, per source, which of the four questions it helps answer and what it can't
do.

**Why:** The scoring can only use data you've actually seen. Real projects fail when the design
assumes data that doesn't exist. Here, we already know Anchorage is missing from the fare data. The
saved samples also become **test fixtures**, so tests run offline and never depend on an API being up.

**Alternatives:**
- *Paid APIs* (FlightAware, Cirium, OAG). Better data, but they cost money, need approval and aren't
  "public". Name them in the design doc as the production upgrade.
- *BTS T-100 segment data* (seats, load factors and departures per route: the ideal capacity data).
  It's a web-form download, not an API, and large. Mention it as the next data source.
- *Scraping airport websites.* Fragile, and of unclear legality.

**Also:** spend 15 minutes on `docs/DOMAIN_NOTES.md`. Check the top claims against their primary sources
(the FAA PFC page, the SNA settlement agreement, SFO's runway data) and mark each verified, corrected
or dropped. These feed the Expansion Friction inputs in Step 2.

**You own:** running the calls and writing the notes in your own words.

## Step 2 — Scope and KPI design (1:00) — your decisions
**What:** Decide what "promising for terminal expansion" means as numbers. Claude will present
options; you choose and record each choice in `docs/DECISIONS.md` with the reason.

**A strong starting structure** (from the outside research): three dimensions.
- **Capacity Strain**: how overloaded the airport is today. Candidates: NAS-delay minutes per flight
  from BTS (delays the airport and airspace cause, not the airline), and fare premium.
- **Growth**: how fast demand is rising. Candidates: passengers vs 2019 and the last 3 years' trend,
  from DOT Table 1a.
- **Expansion Friction**: what stops capacity being added (legal passenger caps, curfews, no land).
  This is a **penalty from a small curated file** (`data/constraints.yaml`), one entry per airport,
  each naming its source. It's deterministic and auditable, but it's a judgement input, and the
  design doc must say so.

  Score = a·Strain + b·Growth − c·Friction.

Optional secondary output, not part of the score: a rough **PFC capacity** figure, enplanements ×
$4.50. It indicates how much renovation debt an airport could support. Label it an upper bound,
since not every airport charges the full $4.50.

**Questions you'll answer:**
1. **Signals.** Which signals measure "demand is outgrowing capacity"? Candidates:
   - passenger volume (scale);
   - growth since 2019 (momentum);
   - fare premium versus similar-distance markets (pricing pressure suggests a supply shortage);
   - carrier concentration (one dominant carrier means demand is captive, which is a risk or an
     opportunity);
   - delay programs (physical congestion).
2. **Combining them.** Options:
   - weighted sum of percentile ranks: robust to outliers and easy to explain;
   - weighted sum of z-scores: keeps distances between airports, but outliers dominate;
   - multiplicative score: rewards airports strong on everything, and one zero kills the score.
3. **Weights.** Fixed weights you defend, or a few named presets ("growth-focused",
   "congestion-focused") the agent can switch between when asked.
4. **Scope.** Which airports are in? Commercial-service airports in Table 1a, the lower 48, and Alaska
   only through OpenSky questions. What's out: cargo economics, financing, airline strategy,
   construction cost.
5. **Confidence.** How does a score show it rests on thin data? For example, a confidence flag when an
   airport has fewer than N markets or is missing a signal.

**Why:** This is the part they're grading. A simple, well-argued KPI beats a clever, opaque one.

**Alternatives:**
- *Let the model rank airports directly.* It fails the brief's "deterministic" requirement, and can't
  be reproduced or audited.
- *Train an ML model.* There's no labelled "renovation was profitable" data to train on, and it's
  unexplainable in a day.
- *Hard-code friction penalties in Python.* Same numbers, but invisible to a reviewer. A data file
  with a source per line makes the judgement inspectable and easy to change on the follow-up call.

**Lesson:** a KPI is an argument written in arithmetic. Every weight is a claim you should be able to
defend.

## Step 3 — Data layer (1:30)
**What:**
- One small module per source, each returning plain records.
- A file cache under `data/cache/`, so every API is called once and later runs are fast and repeatable.
- A function `airport_metrics(code) -> Metrics` that assembles the signals from Step 2. Every number
  carries its source and "as of" date.

**Why:** Keeping data access at the edges means the scoring never touches the network. The cache
avoids rate limits (OpenSky is strict) and makes demos reproducible. Recording source and date is what
lets the agent say "based on DOT fare data through 2026 Q1".

**Alternatives:**
- *Call APIs live on every question.* Slow, rate-limited, and answers drift during the demo.
- *A database (Postgres or SQLite).* Real infrastructure for a few MB of data. DuckDB is a tempting
  middle ground (SQL over CSV files). Choose it only if the pandas code gets awkward.
- *pandas vs polars.* polars is faster, but pandas is what reviewers read fluently, and our data is
  small.

**Claude drafts; you read** each module and explain it back before it's committed.

## Step 4 — Scoring engine (2:00)
**What:** `scoring.py` contains pure functions:
- normalize each signal;
- combine them with the weights from Step 2;
- return per airport the score, its rank, **each signal's contribution** and a confidence flag.

Tests use the Step 1 fixtures. A small CLI prints the New England ranking.

**Why:** "Each signal's contribution" is what makes the agent's explanation honest. The model narrates
numbers the code computed, so it doesn't invent them. Pure functions plus tests are what let you say
"deterministic" with proof.

**Test ideas:**
- Same input gives the same ranking.
- Raising one airport's growth never lowers its score (monotonicity).
- A missing signal lowers confidence and never crashes.
- Ties are broken by a stated rule.

**Alternatives:**
- *Put the scoring inside the prompt.* Not deterministic, and not testable.
- *A rules engine or config DSL.* Over-engineered for five signals.

**Who writes:** AI agents write the code; you get a file-by-file walkthrough and review it. Then you make a small change yourself (a weight or a rule in `config/scoring.yaml`) to show it can be changed live. Weights live in `config/scoring.yaml`. This is the code they'll ask you to change on the call.

## Step 5 — The agent (2:00)
**What:** Google Gemini through the `google-genai` Python SDK with **function calling** (tool use). The model decides which tool to
call; the tools are thin wrappers over Steps 3–4:
- `rank_airports(region, preset)`;
- `compare_airports(codes)`;
- `airport_profile(code)`;
- `long_haul_share(code, threshold_miles)`;
- `compare_over_time(code, from_version, to_version)`: scores the airport on two snapshots and
  returns each signal's change;
- `demand_pressure(code)`.

The system prompt says:
- numbers come only from tools;
- general knowledge must be labelled as such;
- every answer ends with its assumptions and data dates.

The conversation history is kept, so follow-ups ("and what about Hartford?") work.

**Why:** Tool use is the cleanest split for "where is AI used". The model understands the question,
picks tools and explains the result; the code computes. It's also the honest answer to "how did you
stop it from hallucinating numbers".

**Alternatives:**
- *LangChain or LangGraph.* A big abstraction layer over about 50 lines of loop. It hides exactly the
  reasoning they want to see.
- *Claude Agent SDK.* Built for long autonomous agents with file and shell access. Overkill here.
- *A text-to-SQL agent.* Flexible, but the model would write queries the scoring code never checks,
  which weakens the deterministic story.
- *No model at all, just a form with dropdowns.* Fails "conversational follow-up".
- *Programmatic tool calling / code execution* (the model writes and runs Python for each question).
  It's a real Claude feature for crunching big data inside the conversation. But every answer would
  come from freshly written, untested code, which undercuts "deterministic and auditable". Our tools
  already return small aggregates, so the context-size problem it solves doesn't arise. Mention it in
  the design doc as considered and rejected.

**Vendor isolation:** all model calls live in one module (`llm.py`), so swapping vendors touches one
file.

**Model:** Gemini. Try a **Pro**-tier and a **Flash**-tier model on the four example questions in
Step 7 and keep whichever answers well; Flash is faster and cheaper, Pro is more careful on
multi-tool questions. Take the current model names from Google's docs. All model calls live in
`llm.py`, with the provider and model from environment variables.

**Why Gemini for the agent** (it's built with Claude Code):
- **Native real-time voice.** Gemini's Live API holds a spoken two-way conversation and can call the
  same tools; Claude's API has no audio input or output.
- **An existing paid account.**
- **Text tool use is equivalent for our needs.**

**Keys:** the app only reads the environment variable `GEMINI_API_KEY`. We supply it with
`doppler run -- …`; a reviewer passes their own with `-e` or a local `.env`. It's never in the
image. With no key set, `/health` still works and the chat shows a clear message pointing to the
README.

## Step 6 — Chat UI (2:00, voice +0:30)
**What:** one page in **plain HTML, CSS and JavaScript** (no framework, no build step), served by the
same FastAPI container at `/`. The page talks to `POST /chat`.
- **Streaming answers:** the server sends the answer as it's written (server-sent events), and the
  page shows live tool steps ("Scoring 9 New England airports…") while tools run.
- **Data drawn from tool results, not model text:** ranking tables with a split score bar (Strain /
  Growth / Friction) per airport, so the visuals are exact and deterministic.
- **Markdown answers, sanitised:** render with a small library (e.g. `marked`) and **always** clean
  with `DOMPurify`. Model output is untrusted, and unsanitised HTML from it could inject code into
  the page.
- A **"How I got this"** panel per answer: the tools, their inputs and the numbers returned.
- **Suggested-question buttons** for the four example questions.
- **A data freshness badge** in the header: each source's "as of" date, read from the snapshot
  manifest, turning amber ("stale") past an age threshold.
- **A data version picker** (Latest / 2021-Q4 / 2019-Q4). The badge, the rankings and the agent's
  answers all follow the selected version.
- **Responsive and polished:** works from phone to desktop, automatic light and dark mode, clean
  typography, visible focus states for keyboard users. Load the `taste` and `artifact-design` skills
  for the visual pass.
- **Voice, in stages, so something always ships:**
  1. **Push-to-talk** (bonus, safe): the browser's Web Speech API turns speech into the text
     question. Works with any model, on `localhost` and HTTPS only, in Chrome and Edge (the button
     is hidden elsewhere). Optional: read the answer aloud with `speechSynthesis`.
  2. **Stretch: a "Talk" mode** on Gemini's Live API, a real two-way voice conversation that calls
     the same tools. The browser streams microphone audio over a WebSocket. The API key stays on
     the server: either our server relays the audio, or it hands the browser a short-lived token.
     Voice answers stay short, and the full tables appear on screen. If it isn't solid by the
     deadline, it stays switched off and push-to-talk ships. Budget 3–5 hours; it's the hardest
     piece.

**Why:** the page is the first thing the reviewer sees. Streaming and live tool steps make the
reasoning visible, which is a graded requirement. Plain JavaScript keeps the image to a single
Python toolchain and the code readable in one sitting.

**Alternatives:**
- *React (Vite).* Familiar, with nice components, but it adds a Node build stage and a second
  toolchain, and about 3× the code for one page. Right when the UI grows; the design doc says so.
- *Streamlit (or Gradio).* Python only and very fast to build, but every Streamlit app looks the same,
  layout control is limited, and voice needs a separate speech-to-text service (OpenAI Whisper or
  `faster-whisper`).
- *A separate frontend on Cloudflare Pages.* Two deployables and cross-site settings for one page.
  Named in the design doc as the path if the UI grows.
- *No streaming.* Simpler, but 10–20 seconds of a blank wait while tools run feels broken in a demo.

## Step 6b — Docker (1:15)
**What:**
- A `Dockerfile`:
  - **two stages** (uv and build tools in the first; a slim runtime with only the virtualenv, code
    and snapshot in the second);
  - the base image pinned to an exact version, with the same Python version as `pyproject.toml`;
  - runs as a **non-root** user;
  - a `HEALTHCHECK` on `/health`;
  - logs to the console;
  - OCI labels for the source repo and commit;
  - the default command `serve`, with `refresh` available as an alternative command.
- `.dockerignore`, so `.git`, caches and any env files never enter the image.
- `docker-compose.yml`: the `serve` service, plus a `refresh` service run on demand
  (`docker compose run --rm refresh`), sharing a volume for the snapshot.
- CI:
  - build the image;
  - run it;
  - check that `/health` reports the commit;
  - check that no secret-like files are inside the image;
  - build for **amd64 and arm64** (buildx), so it runs natively on Apple Silicon.
- On the `v1.0` tag, push to GHCR with the tags `v1.0` and `sha-<commit>`.
- **Verify on your laptop:** `docker compose up`, run the four questions, then
  `docker compose run --rm refresh`.

**Why:** It's the easiest way for a reviewer to run it: no Python setup, one command. Building in CI
proves it works, since we can't run Docker on this server.

**Alternatives:**
- *uv only.* Simple for Python developers, but a non-Python reviewer has to install a toolchain.
  We keep it as the second way to run.
- *A hosted demo.* No setup at all, but it runs on your key and needs a password and a spending
  limit. Optional, last.
- *Building the image on this server.* Docker is deliberately not installed here, and installing it
  costs memory every other project relies on. Your laptop and CI cover it.
- *One container that refreshes on startup.* Simpler, but every start or scale-out would call the
  government APIs, and a refresh failure would take the chat down. Separate jobs fail independently.
- *Kubernetes manifests or Terraform.* That's real deployment code with no target to deploy to. A
  paragraph describing the deployment shows the same understanding without unverified code.

## Step 6d — Stretch: Refresh on this machine or GitHub Actions (2:30–3:00)
**What:**
- **A `refresh` workflow** (`.github/workflows/refresh.yml`):
  - triggered manually through the API (`workflow_dispatch`) or weekly on a schedule;
  - runs download → validate → transform → compare on GitHub's machine;
  - **publishes a data release** (a GitHub Release `data-YYYY-MM-DD` with the snapshot and manifest
    as files), with the comparison summary as its notes;
  - one run at a time (a concurrency group).
- **The app at startup:** downloads the latest data release (public repo, no token), falling back to
  the baseline snapshot baked into the image. It's held in memory, so no volume is needed.
- **A "Data" settings panel** (gear icon; framed as an architecture demo, since in production
  this is a deployment setting, not a user choice):
  - the freshness badge, plus **who built the current data** ("this machine, 14:03" or "GitHub
    Actions run #12");
  - a toggle **Refresh on: This machine | GitHub Actions**, with a **[Refresh]** button and
    **[Get latest data]**:
    - **This machine** runs `refresh` as a background process **inside the serve container** (not a
      new container: giving the app the Docker socket is a security anti-pattern). One at a time,
      with progress per source, then the comparison summary. Enabled only when
      `ALLOW_LOCAL_REFRESH=true` (default in local compose, **always false on public
      deployments**).
    - **GitHub Actions** starts the workflow through the API, polls the run's status for progress,
      then downloads the data release. Enabled only when `GITHUB_TOKEN_REFRESH` is set (maintainer
      only; fine-grained, *Actions: write* on this repo; server-side only).
    - A disabled option is greyed out **with its reason** ("Disabled on this deployment" or "Needs
      a maintainer token; use Get latest data").
  - **One working store:** `serve` always reads the local data folder. A GitHub refresh downloads its
    release into that folder when done, so there's one place to read and GitHub is a remote producer.
  - On a public deployment, limit triggers (for example one per hour).
- **Notify:** GitHub notifies you about workflow runs. If `NOTIFY_WEBHOOK_URL` is set, the app also
  posts the summary to Slack or Discord.

**Why:** heavy work never runs on a laptop or the demo server, the app stays small and stateless,
and **data versions are separate from code versions**. New data reaches every running copy without a
rebuild, and rolling back bad data means pointing at the previous data release.

**Tradeoffs to state in the design doc:**
- Publishing straight from the workflow skips human review; validation plus the comparison summary
  are the guards. The stricter option is for the workflow to open a PR and wait for approval.
- Fresh data depends on GitHub being up, but the app always works on the baseline snapshot.
- A trigger token on a server is a credential. It's scoped to this one repo's Actions only, and
  never present on public or reviewer copies.

**Alternatives:**
- *Only inside the app container:* simple, but needs a few hundred MB of memory, too much for a
  small server, and anyone with the page could trigger heavy work. That's why it's one option,
  switched off on public deployments.
- *CI refresh → PR → new image* (the default flow): fully reviewed, but every data update is a
  redeploy.
- *A worker plus a queue (Redis):* right at scale, too much for a demo.

## Step 7 — Evaluate and harden (1:00)
**What:**
- Run the four example questions plus traps: an airport we don't cover, a nonsense code, "what's the
  ROI in dollars?", a follow-up that changes the region.
- Save the transcripts to `docs/examples/`.
- Fix what's wrong.
- Add a small automated check that each tool returns the same numbers twice.

**Why:** "Verify before saying done". The example transcripts are also the best evidence you can hand
a reviewer.

**Alternatives:** an LLM-graded eval suite. Valuable at scale; for four questions, reading them
yourself is faster and more honest.

## Step 8 — Design doc and README (1:30) — you write
**What:** `docs/DESIGN.md`, a skeleton already in place:
- architecture diagram;
- scoring methodology;
- key tradeoffs (from `DECISIONS.md`);
- where and how AI is used;
- assumptions, uncertainty and scope;
- what you'd do next.

`README.md`: what it is, setup, run, test, and **"How I work with AI"**. In your own words, describe the
system you've built for AI-assisted engineering:
- written standards the AI must follow;
- separate worker and reviewer agents;
- guards that stop secrets and unsafe commands;
- decisions logged as they happen;
- what was AI-drafted in this repo vs what you decided and wrote.

End with an offer to demo the full setup live on the call. Describe the system; don't link or paste
its internals (it holds other clients' details).

**Why:** It's half the deliverable, and the doc they'll read first.

## Step 9 — Hand-in (0:30)
**What:**
- Run a secret scan (`gitleaks`) over the full history.
- Grep the whole history for anything internal: `git log -p --all | grep -n -i -E -f .git/info/leak-patterns` must print nothing. The pattern file is
  local only (inside `.git/`, so it's never committed).
- Check that `.env` is absent from history.
- Build and commit the three point-in-time snapshots (`refresh --as-of 2019-12`, `--as-of 2021-12`,
  latest), and check that a fresh clone runs with only
  `GEMINI_API_KEY` set.
- Record the 2–3 minute video and link it at the top of the README.
- Prepare the call:
  - `docs/DEMO.md`, a demo script: the 4 questions, 2 follow-ups and 1 trap question, in order;
  - rehearse once, running on **your laptop** at `localhost` (browsers only allow the microphone on
    `localhost` or HTTPS);
  - have the video ready as a fallback;
  - know where the weights live, for the "change it live" request;
  - `docs/QA_PREP.md` (local only, not committed), with your own answers to:
    - "Why these weights?"
    - "How would you validate the KPI?" (backtest against airports that did expand)
    - "What breaks at 10× the users?"
    - "How do you stop hallucinated numbers?"
    - "What's the weakest part of this design?"
    - "How would you deploy and update it?"
    - "What if we don't use GitHub, or must keep data on-premises?" (principle 9)
    - "How do I see that data updates change the answers?" (principle 8: the 2021 → latest demo)
  - **The update demo:** start on the 2021-Q4 snapshot, ask the New England question, click "Get
    latest data", show "what changed", then ask again. Say plainly that it replays real history.
- Make the repo public.
- Tag `v1.0`.
- Send the link.

**Why:** Once it's public, it's public forever. Scan before the switch, never after.
