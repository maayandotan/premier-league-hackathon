# Match Intelligence

**Live AI football commentary that adapts to you.** Two AI commentators, a caller and an analyst, explain a match at your level, from someone learning the game to a seasoned analyst, with every claim backed by match data. Ask "why was that a foul?" mid-match and get an answer without missing the action.

Built for the Microsoft × Premier League [Inside the Game](https://github.com/microsoft/insidethegamehackathon) hackathon.

**Live demo:** https://match-intelligence.bluesmoke-35e894bf.francecentral.azurecontainerapps.io (press ▶ Kick off, sound on)

> Work in progress. Design: [docs/architecture.md](docs/architecture.md), [docs/agents.md](docs/agents.md). Deployment: [docs/deploy.md](docs/deploy.md).

## Run locally

**Backend** (Python 3.11+):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
```

**Frontend** (Node 22+), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and press **Start match**.

Copy `.env.example` to `.env` for the Azure keys (not needed for the skeleton yet).

## Tests

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest
cd frontend && npm run lint && npm run build
```

## Repo layout

| Path | What |
|---|---|
| `backend/` | FastAPI app: events, stats engine, agents, speech |
| `frontend/` | React + TypeScript UI |
| `docs/` | Architecture and schema docs |
| `data/synthetic/` | Generated matches |
| `assets/audio/` | Crowd sound (licensed, see credits) |
| `spikes/` | Throwaway experiments |

## Data

All match data in this project is **synthetic**, with fictional teams and players. See [DATA_POLICY.md](DATA_POLICY.md).

## Credits

- Crowd sound: "Free Crowd Cheering Sounds" by Gregor Quendel, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [assets/audio/CREDITS.md](assets/audio/CREDITS.md).
