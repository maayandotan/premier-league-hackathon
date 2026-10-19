# Event schema

The format every match uses inside the system. The synthetic generator writes it, adapters convert other sources into it, and the stats engine and agents read it.

- **Code:** [`backend/app/events/models.py`](../backend/app/events/models.py) (the source of truth)
- **JSON Schema:** [`event-schema.json`](event-schema.json), generated
- **Example:** [`data/synthetic/sample_match.json`](../data/synthetic/sample_match.json), fictional

Regenerate the last two after changing the models:

```bash
cd backend && .venv/bin/python -m scripts.export_schema
```

## Design

- **Mirrors StatsBomb's open event format.** Same field and type names (`pass`, `shot`, `play_pattern`, `under_pressure`, "Foul Committed"...), so a real provider feed maps over with a thin adapter. See `backend/app/events/adapters/statsbomb.py`.
- **Typed details per event kind** instead of free-form dictionaries: `pass`, `shot`, `carry`, `foul`, `substitution`, `card`.
- **Only what commentary needs.** Adapters drop noise such as "Ball Receipt*", "Starting XI" and "Tactical Shift".

## Coordinates

120 × 80 pitch units. The **x** axis runs from the team's own goal line (0) to the opponent's (120), so every team attacks towards x = 120. **y** runs from the left touchline (0) to the right (80). The goal mouth is y 36–44 at x = 120.

## A match file

```json
{
  "info": {
    "id": "match-001",
    "source": "synthetic",
    "home": {"name": "Northbridge FC", "players": [{"name": "D. Arlo", "jersey_number": 8, "position": "Center Midfield"}]},
    "away": {"name": "Westvale United", "players": []}
  },
  "events": [ ... ]
}
```

## An event

| Field | Type | Notes |
|---|---|---|
| `id` | string | unique |
| `index` | int | order in the feed; replay follows it |
| `period` | int | 1, 2 halves; 3, 4 extra time; 5 penalty shootout |
| `minute`, `second` | int | match clock as on TV (keeps counting: the 2nd half starts at 45:00) |
| `type` | string | see below |
| `team` | string | must match `info.home.name` or `info.away.name` |
| `player`, `position` | string? | |
| `location` | [x, y]? | where the event happened |
| `play_pattern` | string? | "Regular Play", "From Counter", "From Corner", "From Free Kick", "From Throw In"... |
| `under_pressure` | bool | |
| `possession`, `possession_team` | int?, string? | id of the possession sequence; changes when the ball changes team |
| `duration` | float? | seconds |
| `outcome` | string? | for Duel, Dribble, Interception ("Won", "Complete", "Lost"...) |
| `pass` | object? | `recipient`, `end_location`, `length`, `angle`, `height`, `body_part`, `type` (set piece), `technique`, `cross`, `outcome` (default "Complete"), `shot_assist`, `goal_assist` |
| `shot` | object? | `outcome` ("Goal", "Saved", "Off T", "Blocked", "Post"...), `end_location`, `body_part`, `technique`, `type` ("Open Play", "Penalty", "Free Kick"), `first_time`, `provider_xg` |
| `carry` | object? | `end_location` |
| `foul` | object? | `card`, `penalty`, `advantage` (on "Foul Committed") |
| `substitution` | object? | `replacement`, `outcome` |
| `card` | string? | on "Card" events: "Yellow Card", "Second Yellow", "Red Card" |

**Event types:** Pass, Carry, Shot, Dribble, Duel, Interception, Ball Recovery, Clearance, Block, Pressure, Foul Committed, Foul Won, Offside, Card, Substitution, Goal Keeper, Miscontrol, Dispossessed, Injury Stoppage, Half Start, Half End.

## The synthetic generator (#9)

[`backend/app/synthetic/`](../backend/app/synthetic/) generates full 90-minute matches in this format: about 1,200 events each.

- **How it works** (`simulator.py`): a possession-chain simulator. Each possession starts from a restart or a turnover and moves one action at a time (pass, carry, dribble, cross, shot) until the ball is lost, goes out, a foul stops play, or someone shoots. The odds depend on where the ball is. The same scenario and seed always give the same match.
- **Tuned with general football knowledge**, never real data (DATA_POLICY.md rule 5): about 25 shots, 2.5 goals, 22 fouls, 3.5 yellow cards and 10 corners a match. `tests/test_synthetic.py` checks these averages.
- **Scenarios** (`scenarios.py`) script the big moments (goals with their style, red cards, big misses, missed penalties) and the simulator plays the rest of the match around them. In a scripted match only the script scores goals or sends players off. `open` has no script.
- **Squads** (`squads.py`): two fictional clubs in a 4-3-3, 18 players each.

Generate the files, then replay one with `?source=synthetic:<name>`:

```bash
cd backend && .venv/bin/python -m scripts.generate_match                    # every scenario, seed 1
cd backend && .venv/bin/python -m scripts.generate_match comeback --seed 7  # one scenario
```

Format details the generator follows: a goal is a Shot with `shot.outcome == "Goal"` (there's no separate goal event); a card is on its foul (`foul.card`), not a separate Card event; a Substitution's `player` is the one going off and `substitution.replacement` the one coming on; `Half Start` and `Half End` come once per team.
