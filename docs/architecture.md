# Architecture

Live, level-adaptive football commentary: a match event feed goes in, two AI commentators (a caller and an analyst) come out, explained at the viewer's level, with a crowd in the background. Viewers can ask questions while the match keeps running.

## Flow

```
event source (synthetic generator; StatsBomb open data locally only)
   │  adapter → MatchEvent
   ▼
stats engine (code, not AI): xG, momentum, possession, pass value
   │  exposed to the agents as tools
   ▼
ranking agent ── "how interesting is this?"
   ▼
producer agent ── who speaks, when, for how long, what to drop
   ├──► caller   (short, live, excited on big moments)
   └──► analyst  (the "why", in quiet moments)
   ▼
fact checker ── every claim must match a computed number
   ▼
viewer level (beginner → analyst) + language
   ▼
Azure AI Speech (two voices) + crowd audio ──► browser

viewer question 🎤 ──► speech-to-text ──► Q&A agent ──► answer (match keeps running;
                                                         only urgent events interrupt)
```

## Where each part lives

| Part | Folder |
|---|---|
| Event model and adapters | `backend/app/events/` |
| Match replay (live feed simulation) | `backend/app/match/` |
| Stats engine | `backend/app/stats/` |
| Agents and the commentary pipeline | `backend/app/agents/` |
| Speech (TTS, STT) | `backend/app/speech/`, prototype in `spikes/speech/` |
| API and WebSocket | `backend/app/main.py` |
| UI, audio playback | `frontend/src/` |
| Crowd sound | `assets/audio/` |

## WebSocket messages (`/ws/match`)

```json
{"type": "event", "event": {...MatchEvent}}
{"type": "commentary", "line": {"speaker": "caller", "excitement": 2, "text": "GOAL!", "event_id": "..."}}
{"type": "end", "stats": {...}}
```

## Azure

Everything runs in resource group `rg-pl-hackathon`, region **francecentral** (our subscription only allows francecentral, italynorth, austriaeast, switzerlandnorth, israelcentral).
