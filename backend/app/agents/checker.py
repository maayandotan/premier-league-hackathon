"""Checks the Analyst's line against the stats before it's spoken: the first piece of the
Fact-Checker (#17).

Better prompts made mistakes rarer but never zero: with every fact grouped by team, Sonia still
said "Westvale had more of the ball" (they had 35%) or called a half chance "a big chance" about
one line in three at beginner level, where she rephrases numbers in words. So code checks:

- every number she says is one we gave her (no invented xG)
- "more of the ball" / "more shots" / "fewer shots" sit with the right team
- the chance label matches the shot's real label
- on a goal, "X's goal" / "X scored" names the team that scored

Plain rules, not a model: instant, predictable, and testable. They only catch what they look for.
"""
import re

from app.events.models import MatchEvent
from app.stats.engine import StatsEngine

BALL_PHRASES = r"more of the ball|the ball more|most of the ball|more possession|most possession|" \
               r"dominated possession|controlled the ball|had the ball"
LABELS = ("big chance", "half chance", "low-probability")


def _team_before(text: str, position: int, teams: dict[str, str]) -> str | None:
    """The team named closest before a position in the same sentence."""
    sentence_start = max(text.rfind(".", 0, position), text.rfind("!", 0, position)) + 1
    before = text[sentence_start:position]
    found = {team: before.rfind(short) for short, team in teams.items() if before.rfind(short) >= 0}
    return max(found, key=found.get) if found else None


def check_line(text: str, event: MatchEvent, stats: StatsEngine, allowed_numbers: set[str]) -> list[str]:
    """What's wrong with a line, in words the model can act on. Empty if nothing we check is wrong."""
    problems = []
    teams = {team.split()[0]: team for team in (stats.home, stats.away)}  # "Northbridge" -> full name
    possession = stats.possession(recent=True)
    shots = stats.recent_shots()

    for number in set(re.findall(r"\b\d+(?:\.\d+)?\b", text)) - allowed_numbers:
        problems.append(f"the number {number} is not in the FACT lines")

    ball_team = max(possession, key=possession.get)
    if abs(possession[stats.home] - possession[stats.away]) >= 10:
        for match in re.finditer(BALL_PHRASES, text, re.I):
            named = _team_before(text, match.start(), teams)
            if named and named != ball_team:
                problems.append(f"you gave {named} more of the ball, but {ball_team} had it "
                                f"({round(possession[ball_team])}%)")

    if shots[stats.home] != shots[stats.away]:
        more = max(shots, key=shots.get)
        fewer = min(shots, key=shots.get)
        for phrase, right in (("more shots", more), ("fewer shots", fewer)):
            for match in re.finditer(phrase, text, re.I):
                named = _team_before(text, match.start(), teams)
                if named and named != right:
                    problems.append(f'you wrote "{named} ... {phrase}", but {right} had {phrase.split()[0]} '
                                    f"({shots[more]} to {shots[fewer]})")

    if event.is_goal:
        scorer = event.team
        pattern = (r"\b(\w+)(?: United| FC)?(?:['’]s(?: \w+)? goal| scored| score| scoring)"
                   r"|goal (?:by|for) (\w+)")
        for match in re.finditer(pattern, text):
            named = teams.get(match.group(1) or match.group(2))
            if named and named != scorer:
                problems.append(f"you said {named} scored, but the goal was {scorer}'s")

    if event.shot and (quality := stats.shot_quality(event)):
        for label in LABELS:
            if label in text.lower() and not quality["label"].startswith(label):
                problems.append(f'you called it a "{label}", but it was a {quality["label"]}')
    return problems


def numbers_in(*texts: str) -> set[str]:
    """Every number that appears in the facts we gave the model (and the 10 of "last 10 minutes")."""
    found = {"10"}
    for text in texts:
        found |= set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    return found
