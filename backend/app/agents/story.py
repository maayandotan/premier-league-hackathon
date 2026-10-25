"""The match story (#30): memory for the agents, and the half-time and full-time recaps.

Two parts, like everything else here (code decides, the model writes):
- MatchLog (code): what happened and what was said on air, with the minute. Exact: goals with the
  score and the route of the attack, red cards, penalties, big chances, each tactical pattern the
  moment it first shows up, and Roy's own lines. It's what lets him say "as we said at 64'"
  truthfully: code finds the line he really said.
- Storyteller (model): turns the log into a short story every STORY_EVERY match minutes, in the
  background (never on the live path), and writes the recaps at the viewer's level. Checked like
  the other agents: no number that isn't in what it was given; if it fails, the old story stays.
"""
import asyncio
import logging
import re
from dataclasses import dataclass

from agent_framework import Agent

from app.agents.checker import numbers_in
from app.agents.client import chat_client
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

STORY_EVERY = 5 * 60  # match seconds between story updates
DEADLINE_SECONDS = 10.0  # background work: it can take its time, but not forever
RECAP_WORDS = 55
PATTERN_GAP_MINUTES = 10  # a pattern is logged again only after it was gone this long (no flicker)

INSTRUCTIONS = """You keep the story of a live football match for a TV broadcast team.

From the LOG (what happened and what was said on air, with minutes) and the PREVIOUS STORY,
write the STORY so far: 2-3 short sentences, at most 60 words. Cover who has been on top, the
turning points, and any pattern that has built up. It's read by the commentators, not the viewer.

Rules:
- Use only what's in the LOG. Every number must appear in the LOG (scores, minutes, counts).
- Never judge refereeing, never guess what happens next, never invent what nobody logged."""

RECAP_PROMPT = """Write the {which} recap, spoken by the analyst to a {level} viewer:
3 short spoken sentences, at most {words} words. The score, the turning points and one pattern from
the LOG. Every number must appear in the LOG or the FACTS. {level_rule}"""

LEVEL_RULES = {
    "beginner": "Everyday words, explain any football term, at most one number besides the score.",
    "fan": "Clear football language, a number or two. Never say \"xG\".",
    "analyst": "Precise terms; xG and possession % are welcome.",
}


@dataclass(frozen=True)
class Entry:
    minute: int
    kind: str  # goal | red | penalty | chance | pattern | half | said
    text: str
    team: str | None = None


def pattern_kind(pattern: str) -> str:
    """What sort of pattern a line from the detectors is, so it's logged once when it appears."""
    if "down the " in pattern:
        return "channel-" + pattern.split("down the ")[1].split()[0]
    if "opponent's half" in pattern:
        return "press"
    if "quick attacks" in pattern:
        return "transitions"
    if "crosses" in pattern:
        return "crosses"
    return "tilt"


class MatchLog:
    def __init__(self, stats: StatsEngine) -> None:
        self.stats = stats
        self.entries: list[Entry] = []
        self._pattern_seen: dict[tuple[str, str], int] = {}  # (team, kind) -> last minute it was on

    def record(self, event: MatchEvent, moment: Moment) -> list[Entry]:
        """Log what matters about an event (the stats have already seen it). Returns new entries."""
        stats, minute, new = self.stats, event.minute, []
        score = f"{stats.home} {stats.score[stats.home]}-{stats.score[stats.away]} {stats.away}"
        card = event.card or (event.foul.card if event.foul else None)
        if moment.kind == "goal":
            route = stats.patterns.goal_route(event)
            new.append(Entry(minute, "goal", f"GOAL {event.team}, {event.player}: {score} ({moment.reason})"
                             + (f"; the attack {route}" if route else ""), event.team))
        elif card in ("Red Card", "Second Yellow"):
            new.append(Entry(minute, "red", f"red card: {event.player} ({event.team}) sent off", event.team))
        elif moment.reason == "penalty awarded":
            other = stats.away if event.team == stats.home else stats.home
            new.append(Entry(minute, "penalty", f"penalty to {other}", other))
        elif moment.kind == "chance" and moment.score >= 7:
            new.append(Entry(minute, "chance", f"{event.team}: {event.player}, {moment.reason}", event.team))
        elif event.type == "Half End" and event.team == stats.home:
            new.append(Entry(minute, "half", f"end of the {'first' if event.period == 1 else 'second'} half: "
                             f"{score}"))
        for team in (stats.home, stats.away):
            for pattern in stats.patterns.patterns(team):
                key = (team, pattern_kind(pattern))
                last = self._pattern_seen.get(key)
                if last is None or minute - last >= PATTERN_GAP_MINUTES:  # new, not a flicker
                    new.append(Entry(minute, "pattern", f"pattern, {team}: {pattern}", team))
                self._pattern_seen[key] = minute
        self.entries += new
        return new

    def said(self, minute: int, text: str) -> None:
        self.entries.append(Entry(minute, "said", f'Roy said: "{text}"'))

    def earlier_line(self, words: list[str], team: str, before_minute: int, gap: int = 3) -> Entry | None:
        """The latest thing Roy said, at least `gap` minutes ago, that names the team and any of
        the words: what a goal can pay off ("down the right", "pressing high")."""
        short = team.split()[0].lower()
        for entry in reversed(self.entries):
            text = entry.text.lower()
            if (entry.kind == "said" and entry.minute <= before_minute - gap and short in text
                    and any(w in text for w in words)):
                return entry
        return None

    def text(self, last: int | None = None) -> str:
        entries = self.entries[-last:] if last else self.entries
        return "\n".join(f"{e.minute}': {e.text}" for e in entries) or "(nothing notable yet)"


class Storyteller:
    def __init__(self, match_log: MatchLog, use_model: bool) -> None:
        self.log = match_log
        self.story = ""
        self._updated_at: int | None = None
        self.agent = Agent(
            chat_client(),
            name="storyteller",
            instructions=INSTRUCTIONS,
            default_options={"temperature": 0.3, "max_tokens": 220},
        ) if use_model else None

    def due(self, event: MatchEvent) -> bool:
        if not self.agent or not self.log.entries:
            return False
        return self._updated_at is None or event.match_seconds - self._updated_at >= STORY_EVERY

    async def update(self, at_seconds: int) -> None:
        """Rewrite the story from the log. Background work: on failure, the old story stays."""
        self._updated_at = at_seconds
        log_text = self.log.text(last=40)
        prompt = f"PREVIOUS STORY: {self.story or '(none yet)'}\nLOG:\n{log_text}\nWrite the updated STORY."
        try:
            text = (await asyncio.wait_for(self.agent.run(prompt), DEADLINE_SECONDS)).text.strip()
        except Exception as error:
            log.warning("story not updated: %s", type(error).__name__)
            return
        if invented := _invented(text, log_text, self.story):
            log.warning("story rejected, not in the log: %s", sorted(invented))
            return
        self.story = text

    async def recap(self, which: str, level: str, facts: dict[str, str]) -> str | None:
        """The half-time or full-time recap at the viewer's level, or None (then Roy's usual
        summary is used)."""
        if not self.agent:
            return None
        log_text = self.log.text(last=40)
        facts_text = "\n".join(f"{k}: {v}" for k, v in facts.items())
        prompt = (f"LOG:\n{log_text}\nFACTS:\n{facts_text}\n"
                  + RECAP_PROMPT.format(which=which, level=level, words=RECAP_WORDS,
                                        level_rule=LEVEL_RULES.get(level, LEVEL_RULES["fan"])))
        try:
            text = (await asyncio.wait_for(self.agent.run(prompt), DEADLINE_SECONDS)).text.strip()
        except Exception as error:
            log.warning("no recap: %s", type(error).__name__)
            return None
        if invented := _invented(text, log_text, facts_text):
            log.warning("recap rejected, not given: %s", sorted(invented))
            return None
        return text

    def view(self) -> dict:
        """For the Q&A tool: the story so far and the latest logged moments."""
        return {"story": self.story or "(no story yet)", "latest": self.log.text(last=12)}


def _invented(text: str, *given: str) -> set[str]:
    """Numbers, and scorelines like "2-1", that weren't in what the model was given. A scoreline is
    checked whole: "7-0" isn't fine just because a 7 appears elsewhere ("7 crosses")."""
    scorelines = set(re.findall(r"\b\d+-\d+\b", text))
    known_scores = {s for g in given for s in re.findall(r"\b\d+-\d+\b", g)}
    known_scores |= {"-".join(reversed(s.split("-"))) for s in known_scores}  # "Westvale lead 1-0"
    numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", re.sub(r"\b\d+-\d+\b", " ", text)))
    return (scorelines - known_scores) | (numbers - numbers_in(*given))
