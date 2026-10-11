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

## D2: Model tool use, no agent framework (proposed; confirm at Step 5)
- Chose: the model SDK's own tool use (function calling). The model routes and explains; code computes.
- Over: LangChain/LangGraph (heavy abstraction over ~50 lines), text-to-SQL (unchecked numbers), no
  model (fails conversational follow-up).
- Because: it gives the clearest line between AI and deterministic logic, which the brief asks us to
  explain.
- Revisit if: we need multi-step planning across many tools.

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
- Chose: Python 3.13, pinned in `pyproject.toml` (`==3.13.*`) and `.python-version`; uv installs it,
  CI reads `.python-version`, the Dockerfile will use the matching slim image.
- Over: 3.14 (newest and on the dev server, but some libraries and slim images lag), 3.12 (older,
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
