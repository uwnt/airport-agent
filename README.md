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

## Test
_Filled in at Step 4._

## How I work with AI
_Written at Step 8, in my own words: the AI-assisted engineering system I use (standards, worker and reviewer agents, guards, decision log), what was AI-drafted in this repo vs. what I decided and wrote, and an offer to demo the full setup._
