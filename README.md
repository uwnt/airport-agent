# Airport Investment Intelligence Agent

A chat agent that helps analysts find US airports where terminal expansion looks most promising,
using public aviation data, a deterministic scoring model, and Google Gemini for understanding questions
and explaining results.

- Design and scoring methodology: [docs/DESIGN.md](docs/DESIGN.md)
- Build plan and reasoning: [docs/PLAN.md](docs/PLAN.md)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md)
- Adding a data source: [docs/ADDING_A_SOURCE.md](docs/ADDING_A_SOURCE.md)
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

## Run with Docker
Needs only Docker (with Compose); the image runs on amd64 and arm64. A Gemini API key is needed
for free-form questions.

```bash
export GEMINI_API_KEY=...        # your key; it is passed to the container, never built into the image
docker compose up --build
```

Then open http://localhost:8000/. The port is published on `localhost` only. Of the optional
settings, only `GEMINI_MODEL` and `DATA_CHECK_MINUTES` are passed to the container
(`docker-compose.yml`).

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
Each request is also size-limited: a question of at most 2,000 characters, and at most 10 earlier
turns of at most 20,000 characters in total.

`GEMINI_API_KEY` is the only Fly secret, copied from the secrets manager (Doppler) by the deploy
workflow; it is never in the repo or the image. Releases go `dev` → `stg` → `prod`; the `Deploy`
workflow is started by hand on `prod`, builds the image on Fly, and checks that `/health` reports
the deployed commit. **Rollback:** start the same workflow on the previous release tag
(`gh workflow run deploy.yml --ref v1.2.3`); this redeploys that release without moving `prod`.

## Test
```bash
uv run pytest                    # the tests
scripts/ci-local                 # CI's checks (lint, format, tests) except the secrets scan
```

The tests run offline: no network and no model. They cover the scoring, the tools, the data
loading and the server.

## Changing the scoring
Weights, presets and friction penalties live in `config/scoring.yaml`; the constraints behind the
penalties are in `data/constraints.yaml`. Edit those files and restart: no Python is needed.

## How I work with AI
_Written at Step 8, in my own words: the AI-assisted engineering system I use (standards, worker and reviewer agents, guards, decision log), what was AI-drafted in this repo vs. what I decided and wrote, and an offer to demo the full setup._
