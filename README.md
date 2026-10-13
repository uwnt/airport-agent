# Airport Investment Intelligence Agent

A chat agent that helps analysts find US airports where terminal expansion looks most promising,
using public aviation data, a deterministic scoring model, and Google Gemini for understanding questions
and explaining results.

- Design and scoring methodology: [docs/DESIGN.md](docs/DESIGN.md)
- Build plan and reasoning: [docs/PLAN.md](docs/PLAN.md)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md)
- Adding a data source: [docs/ADDING_A_SOURCE.md](docs/ADDING_A_SOURCE.md)
- Demo script for the follow-up call: [docs/DEMO.md](docs/DEMO.md)
- Real-model transcripts of the four example questions and the trap questions: [docs/examples/](docs/examples/)

## Setup
Requires [uv](https://docs.astral.sh/uv/) (it installs the pinned Python 3.13 for you).

```bash
uv sync                                                  # install
```

Settings are read from environment variables; `.env.example` lists the names. Only
`GEMINI_API_KEY` (a Google Gemini key) is needed to chat with the model. The OpenSky credentials
(`OPENSKY_CLIENT_ID`, `OPENSKY_CLIENT_SECRET`) are only for refreshing the data.

## Run
The web chat:

```bash
export GEMINI_API_KEY=...        # your key
uv run uvicorn airport_agent.server:app --host 127.0.0.1 --port 8100
```

Then open http://127.0.0.1:8100/. Voice input needs a model key, `localhost` or HTTPS for the
microphone, and a browser with speech recognition, such as Chrome or Edge; otherwise the
microphone button is hidden. `/health` reports which code is
running (`RELEASE_SHA` in an image, else the local git commit).

Without a key there is no model, so free-form questions are off. The suggested questions and the
picker (rank, compare or profile airports) still run the tools and show their results.

The terminal chat does the same in a shell:

```bash
uv run python -m airport_agent.cli
```

Optional settings (defaults are in `src/airport_agent/llm.py`): `GEMINI_MODEL`,
`GEMINI_THINKING_LEVEL` (minimal, low, medium or high), `MAX_ANSWER_TOKENS`, `MAX_TOOL_CALLS`
(per question) and `REQUEST_TIMEOUT_SECONDS` (per model call).

**Talk mode** (off by default; start the server with `TALK_MODE=on`) adds a Talk button: a spoken
conversation with the agent on Gemini's Live API (`GEMINI_LIVE_MODEL`, default in `llm.py`). The
page streams the microphone to this server over a WebSocket (`/talk`) and the server relays it to
the model, so the key never reaches the browser. The model uses the same tools as typed chat, its
tables appear on screen, and its spoken answers stay short. Each Talk session counts as one
question for the daily cap and ends after 5 minutes, or after a minute with nothing said.
Headphones work best, so the model doesn't hear itself.

**Data panel** (the gear in the header): which data is in use and who built it (baked into the
image, a GitHub data release, or this machine), and three ways to get newer data. Three switches,
all on the server:
- `DATA_RELEASES` (on unless `off`): at startup, and on **Get latest data**, the server downloads
  the newest `data-YYYY-MM-DD` release of this repository (public API, no token) and switches to
  it. It runs in the background; if GitHub can't be reached, the data in the image stays.
  `GITHUB_REPOSITORY` names the repository (default this one).
- `ALLOW_LOCAL_REFRESH=true` enables **Refresh on this machine**: `airport-agent refresh` runs
  inside the server's machine or container. Off by default; keep it off on a public site.
- `GITHUB_TOKEN_REFRESH` enables **Refresh on GitHub Actions**: the server starts the
  `Refresh data` workflow and loads the release it publishes. A fine-grained token with
  Actions: write on this repository only; it stays on the server.

A disabled option is greyed out with its reason. At most one refresh per hour and one "get latest"
per minute per server.

## Run with Docker
Needs only Docker (with Compose); the image runs on amd64 and arm64. A Gemini API key is needed
for free-form questions.

```bash
export GEMINI_API_KEY=...        # your key; it is passed to the container, never built into the image
docker compose up --build
```

Then open http://localhost:8000/. The port is published on `localhost` only. Of the optional
settings, only `GEMINI_MODEL`, `DATA_CHECK_MINUTES`, Talk mode's `TALK_MODE` and
`GEMINI_LIVE_MODEL`, and the Data panel's switches are passed to the container
(`docker-compose.yml`). The `./data` folder is mounted read-only, so for the Data panel's downloads
and local refresh to write into it, drop the `:ro` from the `serve` volume.

## Deploy (Fly)
The live site is https://airport-agent.fly.dev/ (the app name is set in `fly.toml`). It is public
for about two days around the hand-in, so anyone can chat with it, with no sign-in. It sleeps when
idle, so the first visit takes a few seconds to wake it.

The one guard on the model's cost is a **daily cap**: `MAX_MODEL_QUESTIONS_PER_DAY` (300 on Fly,
set in `fly.toml`; unset, as in local and Docker runs, means no cap) limits the questions sent to
the model per UTC day. Over the cap, a free-form question gets a message saying so, and the
suggested questions and the picker still work (they run the tools directly). The count is kept in
memory: the deploy runs a single machine (`flyctl deploy --ha=false`), so the cap is 300 in
total, and the count starts again whenever that machine stops (it sleeps when idle) or restarts.
A second limit, `MAX_MODEL_QUESTIONS_PER_VISITOR_PER_DAY` (20 on Fly; unset means none), counts
each visitor separately, so one visitor can't use up the whole cap.
Each request is also size-limited: a question of at most 2,000 characters, and at most 10 earlier
turns of at most 20,000 characters in total.

`GEMINI_API_KEY` is the only Fly secret, copied from the secrets manager (Doppler) by the deploy
workflow; it is never in the repo or the image. Releases go `dev` → `stg` → `prod`; the `Deploy`
workflow is started by hand on `prod`, builds the image on Fly, and checks that `/health` reports
the deployed commit. Before a deploy from `prod` it also runs the example questions against the
model and stops unless every question gets an answer with no number that a tool didn't give
(`scripts/evaluate.py --check`; skipped for a rollback). **Rollback:** start the same workflow on the previous release tag
(`gh workflow run deploy.yml --ref v1.2.3`); this redeploys that release without moving `prod`.

## Test
```bash
uv run pytest                    # the tests
scripts/ci-local                 # CI's checks (lint, format, types with mypy, tests, snapshot sizes, TODOs need an issue number), not the secrets scan
```

The tests run offline: no network and no model. They cover the scoring, the tools, the data
loading and the server.

## Changing the scoring
Weights, presets and friction penalties live in `config/scoring.yaml`; the constraints behind the
penalties are in `data/constraints.yaml`. Edit those files and restart: no Python is needed.

## How I work with AI
**I decide; AI agents build; I review.** I chose the scope, the measure of "promising" (strain
plus growth), the weights and presets, the friction penalties and the model. AI agents (Claude
Code) wrote the code, each step on its own branch and pull request. I reviewed every step and can
explain and change every part; the weights live in [`config/scoring.yaml`](config/scoring.yaml) so
I can change them live.

How that is kept honest:
- **Written standards** the agents must follow: code style, security and workflow.
- **Separate writers and reviewers.** One agent writes a change; a different agent reads the final
  version of the pull request and records its verdict and findings on it. Each finding is fixed or
  declined with a reason before I merge. Any merged pull request shows the record.
- **Guards** block secrets and unsafe commands. Secrets come only from a secrets manager, never
  from files in the repo, and CI scans every pull request for secrets.
- **Decisions are logged as they happen**: 26 entries in [docs/DECISIONS.md](docs/DECISIONS.md),
  each with what was chosen, what wasn't, and why.
- **Numbers are checked, not trusted**: a tested checker confirms every number in the agent's
  evaluation answers comes from a tool result ([docs/examples/](docs/examples/)).

I'm happy to demo the whole setup live on the call.
