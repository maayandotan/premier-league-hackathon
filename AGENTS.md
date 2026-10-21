# AGENTS.md: read this before working on the repo

Instructions for AI coding agents (GitHub Copilot agent mode, Claude Code, others) and the people driving them. It says what the project is, the rules that can't be broken, how to run and ship it, and what we've learned building the AI agents. Keep it up to date when any of that changes.

## The project

**Match Intelligence**: live AI football commentary that adapts to the viewer, built for the Microsoft × Premier League [Inside the Game](https://github.com/microsoft/insidethegamehackathon) hackathon.

- Two AI commentators: **Guy** (the caller, play-by-play) and **Sonia** (the analyst, explains why a moment mattered).
- Three viewer levels: **beginner**, **fan**, **analyst**. The same moment is explained differently for each.
- Viewers ask questions by voice or text mid-match ("why was that a foul?"). **The match never pauses** while Sonia answers.
- Every number is computed by code (the stats engine) and given to the agents as tools. Agents never invent numbers.
- Team: Maayan (`maayandotan`, repo owner, Azure subscription owner) and Dean (`deanbazak-eng`).
- **Submission due 2026-10-27, 11:59 PM PT.** The live site must stay up until judging ends on 2026-11-10.

Design docs: [docs/agents.md](docs/agents.md) (agent architecture), [docs/architecture.md](docs/architecture.md), [docs/event-schema.md](docs/event-schema.md), [docs/deploy.md](docs/deploy.md).

## Hard rules

Breaking one of these can disqualify the entry. If a task seems to need breaking one, stop and ask.

1. **Data policy ([DATA_POLICY.md](DATA_POLICY.md)).** Real data (StatsBomb) is for testing code locally only. It lives in `data/real/` (git-ignored) and never enters the repo, tests, fixtures, docs, screenshots or the video. Nothing in the submission may be derived from it: the synthetic generator and any model are tuned with general football knowledge, never with numbers computed from real data.
2. **Everything in the demo is fictional.** No real player names, club names, badges or logos anywhere. Our teams (Northbridge FC, Westvale United...) and crests are our own.
3. **No secrets in git.** Keys go in `.env` (git-ignored). Never paste keys into code, docs, commits, issues or chat. Production uses managed identity, not keys, wherever possible.
4. **Third-party assets must be CC0 or CC BY** (commercial use allowed), recorded in a `CREDITS.md` next to the files and credited in the README and video description. The crowd audio is CC BY 4.0 (Gregor Quendel, see `assets/audio/CREDITS.md`).
5. **The repo will be public** at submission, and everything submitted is licensed to Microsoft and the Premier League. Write code and docs as if the judges are reading them, because they will.

## Repo map

| Path | What |
|---|---|
| `backend/app/main.py` | FastAPI app: `/ws/match` WebSocket, `/api/speech-token`, serves the built frontend |
| `backend/app/agents/` | The AI agents and the pipeline that decides who speaks (see below) |
| `backend/app/stats/` | Stats engine (`engine.py`), moment ranker (`ranker.py`), xG (`xg.py`), tactical patterns (`patterns.py`): plain code, exact numbers |
| `backend/app/events/` | Event models (`models.py`, the schema's source of truth) and adapters |
| `backend/app/match/` | Replay and match sources (`demo`, `synthetic:<name>`, `statsbomb:<id>` local only) |
| `backend/app/speech/` | Azure Speech: TTS with SSML styles, browser STT token |
| `backend/tests/` | pytest; runs with no Azure access (`conftest.py` turns agents and speech off) |
| `frontend/src/` | React + Vite + TypeScript: scorebug, SVG pitch, commentary feed, question box, audio engine |
| `backend/app/synthetic/` | Synthetic match generator: possession-chain simulator, scripted scenarios, fictional squads |
| `data/synthetic/` | Generated matches (in git): `comeback`, `red_card`, `late_equaliser`, `open` |
| `spikes/` | Throwaway experiments, step by step versions of the agents. Not production code |
| `scripts/deploy.sh` | Build and deploy to Azure |

### The agents (`backend/app/agents/`)

| File | Role |
|---|---|
| `pipeline.py` | The producer: ranks every event, decides when Guy calls, when Sonia analyses (45 s cooldown), answers questions, falls back to templates |
| `caller.py` | Guy. No tools, must answer within ~2 s, otherwise a template line is used |
| `checker.py` | Checks Sonia's lines and Q&A answers before they're spoken (Q&A against what its tools returned) |
| `analyst.py` | Sonia. Code picks the angle and hands her the facts (grouped by team) in one call; word limits per level |
| `qa.py` | Answers viewer questions with `get_events_before`, `get_key_moments`, `get_rule`, `get_tactic`, `get_match_picture` and shot and pass tools |
| `tactics.py` | Loads the tactics playbook ([docs/football_tactics.md](docs/football_tactics.md)) into concepts; code picks the one a moment or question needs |
| `viewer.py` | Viewer profile (level) |
| `describe.py` | Turns an event into unambiguous fields for the models (e.g. `fouling_team`, `awarded_to`) |
| `client.py` | The Foundry chat client (Entra ID auth) |

Stack: Microsoft Agent Framework (`agent-framework-core`, `agent-framework-foundry`) on Microsoft Foundry, model `gpt-4.1-mini`. Agents are Python `Agent` objects with Python functions as tools and Pydantic `response_format` for structured output. They are created in code when the app runs, so they don't appear on Foundry's Agents page.

## Run it locally

Needs Python 3.11+, Node 22+, the Azure CLI, and a `.env` at the repo root (get it from Maayan privately, see `.env.example` for the names).

```bash
az login            # your BGU account: the agents use Entra ID, not a key

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and press **Kick off** (sound on). URL options: `?source=synthetic:comeback&speed=20&start=80` (match, replay speed, start minute). A fast way to reach full time: `?speed=400`.

Settings in `.env` or the environment: `USE_AGENTS=false` (template commentary, no Azure), `USE_SPEECH=false` (text only), `ALLOW_REAL_DATA` (false in production).

## Before every commit

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q
cd frontend && npm run lint && npm test && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same on every PR. Add a test for every bug fixed and every new tool or rule.

## Git workflow

- Branch from `main` (`feat/...`, `fix/...`, `docs/...`), open a PR, and merge once CI is green. Never push to `main` directly.
- Small PRs with a clear description: what changed and why, how it was tested.
- Commit messages: a short summary line, then why.
- Don't commit generated junk: `.venv`, `node_modules`, `dist`, `__pycache__`, editor files, stray screenshots.

## Deploy

Live: https://match-intelligence-live.purplesand-eefdeaf2.francecentral.azurecontainerapps.io

```bash
scripts/deploy.sh   # builds the image locally (linux/amd64), pushes it to ACR, updates the Container App
```

Details in [docs/deploy.md](docs/deploy.md). Things that will bite you:

- **Azure for Students allows resources only in** francecentral, italynorth, austriaeast, switzerlandnorth, israelcentral. Ours are in **francecentral**, in resource group `rg-pl-hackathon`.
- **ACR cloud builds (`az acr build`) are blocked** on the student subscription. Build locally with `docker buildx --platform linux/amd64`.
- The Container Apps environment must be **workload profiles**, not express: express environments reject updates when the app has a managed identity.
- Only the subscription owner (Maayan) can register resource providers. If you get `AuthorizationFailed ... register/action`, ask him. Dean has Contributor, Cognitive Services User and Azure AI Developer on the resource group.
- Budget is small ($100 credit, $40/month alert). Don't create new paid resources without asking.

## How we build the AI agents: lessons learned

These came from real failures. Follow them when changing or adding an agent.

1. **Code decides, the model writes.** Excitement level, the analysis angle, who speaks and when are decided in Python. The model only turns a decision into words.
2. **Give the model structured, unambiguous input.** Labelled fields, not prose. Sonia once said a penalty helped the wrong team because "team" was ambiguous on a foul; now events say `fouling_team` and `awarded_to`.
3. **Tools return words, not numbers we don't want spoken.** A tool returning `momentum: -0.3` got read out as "momentum value minus zero point three". Return "Westvale on top" instead, and only the numbers the viewer should hear.
4. **One complete tool beats five partial ones.** The Q&A agent made unsupported claims when it had to combine several tools; `get_match_picture` gives the whole picture in one call.
5. **The model can't see the video.** It must never judge a referee's decision, whether a foul was clear or whether a player was unlucky. "Was it deserved?" is answered with data (who was on top, chance quality).
6. **Ask the model to shorten, don't cut its text.** Cutting to a word limit lost the punchline. If a line is too long, ask once to shorten it.
7. **Every model call has a deadline and a fallback.** Live commentary can't wait: Guy falls back to a template after ~2 s, with retries on connection errors. A viewer who asked a question always hears an answer.
8. **Questions carry their match time** so the agent can resolve "that" and "just now". After full time, questions are about the whole match.
9. **Every number comes from a tool** and is checked by a test. The model never computes or recalls a stat.
10. **Don't hand the model a conclusion to support.** "Show who had been dominating" assumed the team on top also had the ball. When Northbridge had 65% of the ball but Westvale had the chances, Sonia gave Westvale the 65% to fit the story (3 out of 3 times). The code now checks the data first and picks an angle that is true (`angle_for` in `analyst.py`, `SPLIT` vs `CONTRAST`).
11. **Knowledge needs its limits.** Given the playbook's idea of pressing but nothing measuring it, Q&A answered "yes, Northbridge are pressing high" and used possession as proof. Every concept now tells the agent what we can measure in this match, or plainly "nothing yet" (`app/agents/tactics.py`).
12. **Hand over facts, grouped by team; then check.** Tool round trips made Sonia take ~6 s against a 7 s deadline; code now gathers her facts and she writes in one call (~2-3 s). Listed by topic, she re-paired numbers with the wrong team; grouped by team, much less. Prompts never get it to zero, so `checker.py` checks every line in code (numbers, possession, shots, chance label, scorer): one retry, then silence.
13. **Check the checker on real answers.** A clause-wide "overall" rule rejected a true answer ("better chances overall and more possession in the last 10 minutes"), which would have told viewers "ask me again" for nothing. Run real questions and read every rejection; every false alarm becomes a test (`tests/test_qa_check.py`).
14. **Calibrate pattern claims on data with no pattern in it.** At first bars, a match with no tactics "showed" field tilt in a third of checks: random data always looks like something. The thresholds in `patterns.py` were raised until style-less matches stay quiet, and the generator's team styles (`Style` in scenarios) were made strong enough to stand out. Also: say "open play" instead of leaving it out; a gap got filled with "from a corner".
15. **Never put example numbers in instructions.** "58 percent of the ball" as a phrasing example came back as a fact. Use placeholders ("N percent").
16. **Test prompts by running them.** Look at real outputs at all three levels before calling an agent done. Reproduce a bad line with a spike that asks the real agent several times and counts failures (`spikes/agents/possession_step_a.py`), then rerun it after the fix. The step by step versions in `spikes/agents/` show how each agent was built.

## Open work

Open issues: `gh issue list`. Current owners and priorities:

- **Synthetic generator v1 (#9) is done**: see [docs/event-schema.md](docs/event-schema.md#the-synthetic-generator-9). Regenerate with `.venv/bin/python -m scripts.generate_match` after changing it.
- **Dean: the demo match scenario (#25).** Pick or tune the scenario the video tells (`backend/app/synthetic/scenarios.py`): which moments, at what minutes, so 2 minutes of video show goals, Sonia explaining, and a viewer question.
- Demo video under 2 minutes (#26), submission package with the repo made public (#27).
- Before 2026-10-27: set the live app to `--min-replicas 1` so judges never hit a cold start.
- Optional if time allows: Fact-Checker (#17), Storyteller (#30), Hebrew commentary (#23), xG trained on synthetic data with SHAP (#11), a fuller Producer (#16), tracing agent runs to Application Insights.
