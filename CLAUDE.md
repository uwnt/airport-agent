# Airport Investment Intelligence Agent (take-home)

A one-day take-home: an AI agent that helps investment analysts find US airports where terminal
expansion is most promising. It uses public aviation data, deterministic scoring, and Google Gemini
with tools behind a chat UI (built with Claude Code). The full brief, the timeline and the reasoning for every step are in
`docs/PLAN.md`. What to do next comes from the pinned "Product roadmap" issue; `docs/PLAN.md` holds
the reasoning behind each step.

## How this project runs
- **Branches:** work branches off `dev` and merges back by PR; `stg` and `prod` are release branches.
  There is no staging environment: `stg` is a pass-through. A release is cut to `stg`, promoted to
  `prod`, and then deployed to Fly by a manually started workflow on `prod`. Production deploys are
  the owner's. `main` holds only the first setup commits and takes no new work.
- **Phases:** `phase:1` = everything needed for the hand-in (plan Steps 0–9); `phase:2` = before the
  follow-up call (the stretch steps); `phase:3` = debt and housekeeping.
- **Plan:** the pinned "Product roadmap" issue is the ordered index; each plan step has its own issue.
- The owner's GitHub account name may appear in public text (repo URL, commit emails, comments).

## How to work in this repo: teaching mode
The owner is building this to learn and will defend it in a follow-up call. For **every** step:
1. **Before acting:** say what we're doing and why, the main alternatives, and why we're not choosing
   them. Keep it short and plain; define a term the first time it appears.
2. **The owner is new to Python. The goal is that they understand and can change every part,
   not that they type it.**
   - The owner **decides** scope, KPI and weights. Present options with a recommendation; never pick
     silently.
   - **Claude writes the code**, in small pieces. After each piece, give a short plain-English
     walkthrough, then ask the owner to explain it back or predict what a change would do.
   - **The scoring is built together** (`scoring.py`, `config/scoring.yaml`, their tests). Write a
     few lines at a time; after each, the owner makes the *next* small change themselves (a weight,
     a rule, a new signal), with hints. They must be able to change it live on the call.
   - **Weights, presets and friction penalties live in `config/scoring.yaml`**, not in code, so a
     live change needs no Python.
   - The owner **writes `docs/DESIGN.md` and the README's "How I work with AI"** in their own words;
     Claude reviews. Don't write these for them.
   - At the start of Step 4, run a **45-minute Python crash course on this project's own code**:
     variables, functions, lists and dicts, `if` and loops, basic pandas, reading a traceback,
     running pytest. Nothing beyond what the project uses.
   - End every step with a **code tour**: what was written, file by file, in plain words.
3. **After each step:** ask one or two quick questions that check understanding ("what happens if
   OpenSky is down?"), then log any decision in `docs/DECISIONS.md` and tick the step in `docs/PLAN.md`.

## Rules for this repo
- **The repo will be public.** Nothing in it may reveal secrets, internal server details or other
  projects. No internal server paths, internal issue numbers, or names of other projects or organisations
  (the owner's own GitHub account name excepted) in files, commits,
  issues or PRs. Before every push, and before posting any issue, PR or comment text, check it:
  `grep -n -i -E -f .git/info/leak-patterns <files or text>` must print nothing. Reviewer agents
  carry server-wide rules, so rewrite their findings in plain words before posting.
- **Secrets live only in Doppler** (project `airport-agent`, config `dev`). Run with
  `doppler run -- <cmd>`. Never print a secret, never write `.env`. `.env.example` lists names only.
- **GitHub uses the owner's token, per command:** `doppler run -- gh …` (sets `GH_TOKEN` for that
  command only). Never run `gh auth login` or `gh auth switch`: the machine's login belongs to other
  work.
- **Small commits:** imperative subject ≤ 72 chars, body says why. One branch and PR per issue,
  with an issue per step; merged by the owner.
- **The owner's AI workflow is shown on purpose, in readable form** (it's part of what this repo
  demonstrates):
  - Each PR body has **What / Why / Tested** (the exact commands run and their result) and
    **Decisions** (links to `docs/DECISIONS.md` entries).
  - Before merge, each PR gets an **independent AI review**: dispatch the `reviewer-sonnet` agent
    with a short card (the PR's diff, its goal, 2–3 risk areas). Post its findings and what was done
    about each as **one plain-English PR comment** headed "Independent AI review".
  - Fix or explicitly decline each finding before the owner merges.
  - No internal jargon in anything public: no round counters, no internal labels, no server tool
    names.
- **Deterministic core:** scoring is pure (no network, no model) and tested. Every number the agent
  states comes from a tool; general knowledge is labelled as such. Domain facts come only from
  `docs/DOMAIN_NOTES.md`, and only those marked ✅ are stated as fact.
- **Least code:** stdlib, then what's installed, then a small well-known dependency, with the reason
  in the PR.
- **The agent's model is Google Gemini** (`google-genai` SDK). Before writing Gemini code, read Google's
  current Gemini API docs for the exact SDK calls and model names. Don't rely on memory: names change
  often. All model calls live in `llm.py`.
- **No Docker on this server, by design.** Never install it. The Docker image is built and tested only
  in GitHub Actions (Step 6b).
- The web chat must never get a public address. Test it via `localhost` (an SSH port forward) or
  the private network only.
- Verify before calling a step done: run it and show the output.

## Commands (fill in at Step 0)
```bash
uv sync                          # install
doppler run -- uv run pytest     # test
uv run ruff check . && uv run ruff format --check .   # lint
scripts/ci-local                 # CI's checks except the secrets scan, before a PR (also: make ci)
doppler run -- uv run python -m airport_agent.cli     # terminal chat (Step 5)
doppler run -- uv run uvicorn airport_agent.server:app --reload   # web chat (Step 6)
```
