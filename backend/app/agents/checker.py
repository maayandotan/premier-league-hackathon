"""Checks the Analyst's line against the stats before it's spoken: the first piece of the
Fact-Checker (#17).

Better prompts made mistakes rarer but never zero: with every fact grouped by team, Roy still
said "Westvale had more of the ball" (they had 35%) or called a half chance "a big chance" about
one line in three at beginner level, where he rephrases numbers in words. So code checks:

- every number he says is one we gave him (no invented xG)
- "more of the ball" / "more shots" / "fewer shots" sit with the right team
- the chance label matches the shot's real label
- on a goal, "X's goal" / "X scored" names the team that scored

Q&A picks its own tools, so code can't know its numbers in advance: every tool records what it
returned for the current question (recorded / recording), and the answer is checked against that:

- every number he says came from a tool (allowing normal rounding: 64.6 -> 65%, 0.188 -> 19%)
- a percentage or xG sits with the team the tool gave it to
- "more shots" / "more of the ball" (whole match or last 10 minutes) name the right team
- a chance is judged only from get_shot_quality, with its label
- no guessing ("likely", "probably")

Plain rules, not a model: instant, predictable, and testable. They only catch what they look for.
"""
import functools
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.events.models import MatchEvent
from app.stats.engine import StatsEngine

BALL_PHRASES = r"more of the ball|the ball more|most of the ball|more possession|most possession|" \
               r"dominated possession|controlled the ball|had the ball"
LABELS = ("big chance", "half chance", "low-probability")
# (phrase, which stat, True if the phrase means the higher value)
COMPARISONS = (("more shots", "shots", True), ("fewer shots", "shots", False),
               ("more possession", "possession", True), ("more of the ball", "possession", True),
               ("less possession", "possession", False), ("less of the ball", "possession", False))
# How people describe a chance -> the shot-quality label it implies
CHANCE_WORDS = (("great chance|excellent chance|very good chance|big chance|huge chance", "big chance"),
                ("half chance|decent chance", "half chance"),
                ("poor chance|hard chance|low-probability|difficult chance", "low-probability effort"))


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


# ---------- Q&A: what the tools returned for this question ----------

_tool_results: ContextVar[list | None] = ContextVar("tool_results", default=None)


def recorded(tool: Callable) -> Callable:
    """The same tool (same name, arguments and description for the model), noting what it returned."""
    @functools.wraps(tool)
    def wrapper(*args, **kwargs):
        result = tool(*args, **kwargs)
        if (seen := _tool_results.get()) is not None:
            seen.append(result)
        return result
    return wrapper


@contextmanager
def recording() -> Iterator[list]:
    """Collect the tool results of one question. Each question has its own list, even when two
    viewers ask at once (tools run in tasks or threads that inherit this context)."""
    seen: list = []
    token = _tool_results.set(seen)
    try:
        yield seen
    finally:
        _tool_results.reset(token)


def _text(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def _ways_to_say(value: float) -> set[str]:
    """How a number can fairly be said: 64.6 -> 65, 0.188 -> 0.19 or 19 (%) or "1 in 5"."""
    ways = {_text(value), _text(round(value)), _text(round(value, 1)), _text(round(value, 2))}
    if 0 < value < 1:
        ways |= {_text(round(value * 100)), _text(round(value * 100, 1))}
        n = round(1 / value)
        ways |= {str(k) for k in (n - 1, n, n + 1) if k > 1}
    return ways


def _walk(value: Any, teams: set[str], found: set[str], by_team: dict[str, set[str]]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        found |= _ways_to_say(value)
    elif isinstance(value, str):
        for number in re.findall(r"\b\d+(?:\.\d+)?\b", value):
            found |= _ways_to_say(float(number))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in teams and isinstance(item, int | float) and not isinstance(item, bool):
                for way in _ways_to_say(item):
                    by_team.setdefault(way, set()).add(key)
            _walk(item, teams, found, by_team)
    elif isinstance(value, list | tuple):
        for item in value:
            _walk(item, teams, found, by_team)


# "scored by Ferro", "a goal from M. Ferro", "Ferro scored", "Ferro headed in": a claim about who scored.
SCORER_CLAIMS = (
    r"\b(?:scored by|goal (?:by|from)|winner from|equali[sz]er from) (?:[A-Z]\.\s?)?([A-Z][\w'-]+)",
    r"\b([A-Z][\w'-]+) (?:scored|has scored|headed (?:it )?in|fired (?:it )?in|found the net)\b(?!\s+\d)",
)


def check_answer(text: str, tool_results: list, stats: StatsEngine, also_allowed: set[str],
                 scorers: set[str] | None = None) -> list[str]:
    """What's wrong with a Q&A answer, in words the model can act on. `scorers`: the surnames of this
    match's goal scorers so far (None skips that check)."""
    teams = {team.split()[0]: team for team in (stats.home, stats.away)}
    allowed, by_team = {"10"} | also_allowed, {}
    _walk(tool_results, set(teams.values()), allowed, by_team)
    problems = []
    for number in sorted(set(re.findall(r"\b\d+(?:\.\d+)?\b", text)) - allowed):
        problems.append(f"the number {number} didn't come from your tools")
    # A percentage or an xG must sit with the team the tool gave it to.
    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)|\b(\d+\.\d+)\b", text):
        number = match.group(1) or match.group(2)
        owners = by_team.get(number, set())
        named = _team_before(text, match.start(), teams)
        if len(owners) == 1 and named and named not in owners:
            problems.append(f"{number} belongs to {next(iter(owners))}, not {named}")
    # Comparisons need the right team too: "Northbridge have more shots (11)" when it's 11 to 12.
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for phrase, key, most in COMPARISONS:
            if phrase not in sentence.lower():
                continue
            at = sentence.lower().index(phrase)
            recent = _period_is_recent(sentence, at)
            values = _find(tool_results, f"{key}_last_10_min" if recent else key)
            if not values or len(set(values.values())) < 2:
                continue
            right = (max if most else min)(values, key=values.get)
            named = _team_before(sentence, at, teams)
            if named and named != right:
                period = "in the last 10 minutes" if recent else "in the whole match"
                problems.append(f'"{named} ... {phrase}" is wrong {period}: '
                                + ", ".join(f"{team} {value}" for team, value in values.items()))
    # Who scored in this match: only someone who did. Season and league goals are a different claim.
    if scorers is not None:
        # (an initial, as in "L. Pirozzi", doesn't end a sentence)
        for sentence in re.split(r"(?<=[.!?])(?<!\b[A-Z]\.)\s+", text):
            if re.search(r"season|league|career|this year", sentence, re.I):
                continue
            for pattern in SCORER_CLAIMS:
                for name in re.findall(pattern, sentence):
                    if name not in scorers and name not in {"He", "She", "They", "Nobody", "No"}:
                        who = ", ".join(sorted(scorers)) or "nobody yet"
                        problems.append(f"{name} hasn't scored in this match (scorers so far: {who})")
    if guess := re.search(r"\b(likely|probably|must have|surely)\b", text, re.I):
        problems.append(f'"{guess.group(1)}" is a guess: say only what the tools show')
    # How good a chance was: only from get_shot_quality, and matching its label.
    labels = {r["label"] for r in tool_results if isinstance(r, dict) and "label" in r and "xg" in r}
    for words, label in CHANCE_WORDS:
        if re.search(words, text, re.I):
            if not labels:
                problems.append("you judged how good the chance was without get_shot_quality")
            elif label not in labels:
                problems.append(f"the chance was a {', '.join(sorted(labels))}, not a {label}")
    return problems


CLAUSE_BREAK = r",|;| but | while | whereas | though | however "
RECENT_WORDS = r"last 10|last ten|recent|lately"
OVERALL_WORDS = r"overall|whole match|so far|in total|all match"


def _period_is_recent(sentence: str, at: int) -> bool:
    """Whether a comparison talks about the last 10 minutes or the whole match. A time qualifier
    usually FOLLOWS what it describes ("more possession in the last 10 minutes", "better chances
    overall"), so look after the phrase within its clause first, then back through the sentence."""
    end = re.search(CLAUSE_BREAK, sentence[at:], re.I)
    after = sentence[at: at + end.start() if end else len(sentence)]
    for text in (after, sentence[:at]):
        found = [(m.start(), name) for name, words in (("recent", RECENT_WORDS), ("overall", OVERALL_WORDS))
                 for m in re.finditer(words, text, re.I)]
        if found:
            nearest = min(found) if text is after else max(found)  # first after, or last before
            return nearest[1] == "recent"
    return False


def _find(value: Any, key: str) -> dict | None:
    """The first dict stored under a key anywhere in the tool results."""
    if isinstance(value, dict):
        if isinstance(value.get(key), dict):
            return value[key]
        value = list(value.values())
    if isinstance(value, list | tuple):
        for item in value:
            if (found := _find(item, key)) is not None:
                return found
    return None
