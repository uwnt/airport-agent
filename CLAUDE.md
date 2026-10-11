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
- **Phases:** `phase:1` = everything needed for the hand-in (plan Steps 0–9, except the stretch steps 6c and 6d);
  `phase:2` = before the follow-up call (the stretch steps 6c and 6d); `phase:3` = debt and housekeeping.
- **Plan:** the pinned "Product roadmap" issue is the ordered index; each plan step has its own issue.
- The owner's GitHub account name may appear in public text (repo URL, commit emails, comments).

## How we work
The owner leads the project and will defend it in a follow-up call. For every step:
1. **Before acting:** say what we're doing and why, the main alternatives, and why we're not choosing
   them. Keep it short and plain.
2. **The owner decides; agents build; the owner reviews.**
   - The owner **decides** scope, KPI and weights. Present options with a recommendation; never pick
     silently.
   - **AI agents write the code** for each step, on a branch with a PR; the PR gets an independent
     AI review before merge (see D6). The owner then goes through it with the AI assistant and must
     be able to explain and change every part.
   - **Weights, presets and friction penalties live in `config/scoring.yaml`**, not in code, so a
     live change needs no Python. After the scoring is written, the owner makes a small change
     themselves (a weight, a rule, a new signal) so they can change it live on the follow-up call.
   - The owner **writes `docs/DESIGN.md` and the README's "How I work with AI"** in their own words;
     the AI reviews. Don't write these for them.
   - End every step with a **code tour**: what was written, file by file, in plain words.
3. **After each step:** log any decision in `docs/DECISIONS.md` and tick the step in the
   pinned roadmap issue (`docs/PLAN.md` keeps the reasoning, not the progress).

## Rules for this repo
- **The repo will be public.** Nothing in it may reveal secrets, details of the development machine
  or its infrastructure, or other projects. No local file paths, issue numbers from other
  repositories, or names of other projects or organisations (the owner's own GitHub account name
  excepted) in files, commits, issues or PRs. Before every push, and before posting any issue, PR
  or comment text, check it:
  `grep -n -i -E -f .git/info/leak-patterns <files or text>` must print nothing. Reviewer agents
  may use internal shorthand, so rewrite their findings in plain words before posting.
- **Secrets live only in Doppler** (project `airport-agent`, config `dev`). Run with
  `doppler run -- <cmd>`. Never print a secret, never write `.env`. `.env.example` lists names only.
- **GitHub uses the owner's token, per command:** `doppler run -- gh …` (sets `GH_TOKEN` for that
  command only). Never run `gh auth login` or `gh auth switch`: the machine's existing GitHub login must
  stay unchanged.
- **Small commits:** imperative subject ≤ 72 chars, body says why. One branch and PR per issue,
  with an issue per step; merged by the owner.
- **The owner's AI workflow is shown on purpose, in readable form** (it's part of what this repo
  demonstrates):
  - Each PR body has **What / Why / Tested** (the exact commands run and their result) and
    **Decisions** (links to `docs/DECISIONS.md` entries).
  - Before merge, each PR gets an **independent AI review**: dispatch an independent reviewer agent
    with a short card (the PR's diff, its goal, 2–3 risk areas). Post its findings and what was done
    about each as **one plain-English PR comment** headed "Independent AI review".
  - Fix or explicitly decline each finding before the owner merges.
  - No internal jargon in anything public: no round counters, no internal labels, no internal tool
    names.
- **Deterministic core:** scoring is pure (no network, no model) and tested. Every number the agent
  states comes from a tool; general knowledge is labelled as such. Domain facts come only from
  `docs/DOMAIN_NOTES.md`, and only those marked ✅ are stated as fact.
- **Least code:** stdlib, then what's installed, then a small well-known dependency, with the reason
  in the PR.
- **The agent's model is Google Gemini** (`google-genai` SDK). Before writing Gemini code, read Google's
  current Gemini API docs for the exact SDK calls and model names. Don't rely on memory: names change
  often. All model calls live in `llm.py`.
- **Never install Docker on the development machine.** The Docker image is built and tested only in
  GitHub Actions (Step 6b).
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
