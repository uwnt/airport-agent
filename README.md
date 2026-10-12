# Airport Investment Intelligence Agent

A chat agent that helps analysts find US airports where terminal expansion looks most promising,
using public aviation data, a deterministic scoring model, and Google Gemini for understanding questions
and explaining results.

- Design and scoring methodology: [docs/DESIGN.md](docs/DESIGN.md)
- Build plan and reasoning: [docs/PLAN.md](docs/PLAN.md)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md)
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

Then open http://127.0.0.1:8100/. Voice input needs `localhost` or HTTPS for the microphone
(and a browser with speech recognition, such as Chrome or Edge). `/health` reports which code is
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

Then open http://localhost:8000/. The port is published on `localhost` only.

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
