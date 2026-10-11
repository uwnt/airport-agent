# Airport Investment Intelligence Agent

A chat agent that helps analysts find US airports where terminal expansion looks most promising,
using public aviation data, a deterministic scoring model, and Google Gemini for understanding questions
and explaining results.

- Design and scoring methodology: [docs/DESIGN.md](docs/DESIGN.md)
- Build plan and reasoning: [docs/PLAN.md](docs/PLAN.md)

## Setup
Requires [uv](https://docs.astral.sh/uv/) (it installs the pinned Python 3.13 for you).

```bash
uv sync                                                  # install
uv run pytest                                            # test
uv run ruff check . && uv run ruff format --check .      # lint
```

Secrets (`GEMINI_API_KEY`, OpenSky credentials) are read from environment variables; see
`.env.example` for the names.

## Run
The web server (for now it only answers `/health`; the chat arrives in Step 6):

```bash
uv run uvicorn airport_agent.server:app --host 127.0.0.1 --port 8100
curl http://127.0.0.1:8100/health   # {"status":"ok","commit":"<git sha>",...}
```

`/health` reports which code is running (`RELEASE_SHA` in an image, else the local git commit).

## Run with Docker
Needs only Docker (with Compose); the image runs on amd64 and arm64. A Gemini API key is
needed once the chat agent lands; until then the server only answers `/health`.

```bash
export GEMINI_API_KEY=...        # your key; it is passed to the container, never built into the image
docker compose up --build
```

Then open http://localhost:8000/health. The port is published on `localhost` only.

## Test
_Filled in at Step 4._

## How I work with AI
_Written at Step 8, in my own words: the AI-assisted engineering system I use (standards, worker and reviewer agents, guards, decision log), what was AI-drafted in this repo vs. what I decided and wrote, and an offer to demo the full setup._
