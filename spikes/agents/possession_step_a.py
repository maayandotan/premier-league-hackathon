"""Possession mix-up, Step A: reproduce it.

At the comeback's 88' winner the data disagrees with itself: Northbridge had ~65% of the ball in
the last 10 minutes, but Westvale had been more dangerous (momentum). The ranker calls the goal
"against the run of play", and the Analyst's angle says "show who had been dominating".
Sonia once gave Westvale the 65%. Here we ask the real Analyst several times and count how often
a possession % lands on the wrong team.

Synthetic data only. Run from the repo root:
  backend/.venv/bin/python spikes/agents/possession_step_a.py
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.agents.analyst import Analyst, angle_for  # noqa: E402
from app.agents.viewer import ViewerProfile  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.ranker import rank  # noqa: E402

RUNS = 6
TEAMS = {"Northbridge": "Northbridge FC", "Westvale": "Westvale United"}


def misattributed(text: str, possession: dict[str, float]) -> list[str]:
    """Each 'NN%' / 'NN percent' credited to the team named closest before it, if that's wrong."""
    wrong = []
    for match in re.finditer(r"(\d{2})\s*(%|percent)", text):
        number = int(match.group(1))
        before = text[:match.start()]
        named = max(TEAMS, key=lambda short: before.rfind(short))
        if before.rfind(named) < 0:
            continue
        owner = min(possession, key=lambda team: abs(possession[team] - number))
        if abs(possession[owner] - number) <= 3 and TEAMS[named] != owner:
            wrong.append(f"{number}% given to {named}, but it was {owner}'s")
    return wrong


async def main() -> None:
    match = load_source("synthetic:comeback")
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    events_by_id = {e.id: e for e in match.events}
    for event in match.events:
        before = stats.momentum()["value"]
        stats.update(event)
        moment = rank(event, stats, before)
        if event.is_goal and event.minute >= 88:
            break
    truth = stats.possession(recent=True)
    print(f"{event.minute}' {event.player}: {moment.reason}")
    print(f"truth: possession last 10 = {truth}, momentum leader = {stats.momentum()['leader']}")
    print(f"ANGLE: {angle_for(moment, stats)}\n")

    analyst = Analyst(stats, events_by_id, use_model=True)
    failures = 0
    for run in range(1, RUNS + 1):
        line = await analyst.analyse(event, moment, ViewerProfile(level="fan")) or "(silent)"
        wrong = misattributed(line, truth)
        failures += bool(wrong)
        print(f"{run}. {'WRONG' if wrong else 'ok   '} {line}")
        for problem in wrong:
            print(f"         -> {problem}")
    print(f"\n{failures}/{RUNS} lines gave the possession to the wrong team")


if __name__ == "__main__":
    asyncio.run(main())
