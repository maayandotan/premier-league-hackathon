"""Tactics playbook, Step A: does the playbook make the agents better, and do they stay honest?

1. Sonia on the comeback's 18' counter-attack goal, at each level, without and with the TACTICS
   note that code attaches (docs/football_tactics.md, "Counter-attack and transitions").
2. Q&A on tactics and rules questions that the playbook covers.

What to look for: the idea used in her own words; no example numbers or names copied ("third
quick counter"); nothing from do_not_claim ("defenders were back", "switched off").

Synthetic data only. Run from the repo root:
  backend/.venv/bin/python spikes/agents/tactics_step_a.py
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.agents import analyst as analyst_module  # noqa: E402
from app.agents.analyst import Analyst  # noqa: E402
from app.agents.qa import QuestionAnswerer  # noqa: E402
from app.agents.viewer import ViewerProfile  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.ranker import rank  # noqa: E402

COPIED = ["third", "quick counter this half", "ten seconds", "Westvale broke at speed"]
NOT_CLAIMED = ["defenders were back", "switched off", "out of position", "caught", "marking"]


def flags(text: str) -> str:
    found = [w for w in COPIED + NOT_CLAIMED if w.lower() in text.lower()]
    return f"   <- check: {found}" if found else ""


async def main() -> None:
    match = load_source("synthetic:comeback")
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    events_by_id = {e.id: e for e in match.events}
    timeline = []
    for event in match.events:
        before = stats.momentum()["value"]
        stats.update(event)
        moment = rank(event, stats, before)
        timeline.append((event, moment))
        if event.is_goal and event.minute == 18:
            break
    print(f"{event.minute}' {event.player} ({event.play_pattern}): {moment.reason}\n")

    analyst = Analyst(stats, events_by_id, use_model=True)
    await analyst.analyse(event, moment, ViewerProfile(level="fan"))  # warm up
    for level in ("beginner", "fan", "analyst"):
        with patch.object(analyst_module, "concept_for", lambda *args: None):
            without = await analyst.analyse(event, moment, ViewerProfile(level=level)) or "(silent)"
        with_playbook = await analyst.analyse(event, moment, ViewerProfile(level=level)) or "(silent)"
        print(f"[{level}] without: {without}")
        print(f"[{level}] with:    {with_playbook}{flags(with_playbook)}\n")

    qa = QuestionAnswerer(stats, timeline, events_by_id, use_model=True)
    minute, second = divmod(stats.clock, 60)
    for level, question in [("beginner", "Why did that counter-attack work?"),
                            ("fan", "Is it offside if you're level with the defender?"),
                            ("analyst", "Are Northbridge pressing high?")]:
        answer = await qa.answer(question, minute, second, ViewerProfile(level=level))
        print(f"Q [{level}] {question}\nA: {answer}{flags(answer)}\n")


if __name__ == "__main__":
    asyncio.run(main())
