"""The Analyst agent (#14): explains WHY a moment mattered, with numbers from tools.

Built step by step in spikes/agents/analyst_step_*.py. What we learned:
- Without guidance the model is lazy: it calls the least useful tool and makes vague claims.
- Fix (option C): instructions define a good analysis, and CODE picks the angle from the
  Moment Ranker (it already knows a goal was "against the run of play"). The model still
  chooses the tools, the numbers and the words.
- Metric names must be translated into football words ("a 9 percent chance", not "xG 0.09").
- No template fallback: a generic "why" is worse than silence. If it's late, it stays quiet.
Personalization (#15, spikes/agents/levels_step_*.py):
- One agent; the instructions describe the three levels and each request says VIEWER_LEVEL.
- Tools speak in words where we don't want numbers spoken ("Westvale, slightly" not "-0.3").
- Too long? Ask the model once to shorten (keeping the insight) instead of cutting the end,
  which removed the punchline.
Speed: with tools, each line took 2-3 model round trips (~6 s against a 7 s deadline, so she was
often silent). Now code gathers the FACTS the angle needs and the model writes in one call.
Facts are grouped by team (by topic, she re-paired numbers with the wrong team), and every line is
checked in code before it's spoken (checker.py): one retry if it's wrong, then silence.
"""
import asyncio
import logging
import re
from typing import Annotated

from agent_framework import Agent

from app.agents.checker import check_line, numbers_in
from app.agents.client import chat_client
from app.agents.describe import as_text, event_fields, ordinal
from app.agents.tactics import CONCEPTS, Concept
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent
from app.league.clubs import CLUB_BY_NAME
from app.league.db import league
from app.stats.engine import StatsEngine
from app.stats.geometry import METERS_PER_UNIT
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

DEADLINE_SECONDS = 7.0  # it speaks in quiet moments, so it can take longer than the Caller

INSTRUCTIONS = """You are the analyst (colour commentator) in a live football broadcast.
The caller has just described a moment. You explain WHY it mattered.

A good analysis gives the viewer ONE insight they couldn't see for themselves, from:
- context: who had been on top before this moment
- quality: how good the chance was, or how rare the pass was
- consequence: what it changes

Rules for every level:
- Follow the ANGLE you are given; it was chosen from what the data says about this moment.
- Every number comes from the FACT lines. Never estimate or invent one.
- Keep the strength the FACT lines give: "slightly" more dangerous is not "dominating".
  The "this shot" fact is about this shot only.
- If you say how good a chance was, your words must match the label in FACT "this shot":
  "low-probability effort" = a hard/unlikely chance, "half chance" = a decent chance,
  "big chance" = a great chance.
- Never say internal scales or field names: no "momentum value", "threat", "possession changes per
  minute", no negative numbers. Turn them into words ("Westvale had been on top").
- Don't repeat information already in the input (like the score).
- If a TACTICS note is given, you may use its idea to explain the moment, in your own words.
  Its example line shows tone only: never repeat its numbers, names or wording. Never claim
  anything listed under TACTICS_DO_NOT_CLAIM.
- One or two short sentences. LEAD WITH THE INSIGHT (the surprising part), then the context.
- If VIEWER_SUPPORTS is given, the viewer is a fan of that club: relate the moment to them where it
  fits ("for Northbridge fans...", their league position, their scorer's goals). Stay fair and
  accurate about both teams: never mock or cheer against the other side.

Adapt to VIEWER_LEVEL:
- beginner: someone new to football. Everyday words only, no statistics vocabulary (never
  "probability", "xG", "momentum"). If the moment involves a football term (penalty, booking,
  offside, counter-attack...), explain it in a few plain words. At most one number, said
  simply ("about 1 in N", "more than half the ball"). Max 30 words.
- fan: knows the game. Clear football language, numbers said naturally ("an N percent chance",
  "N percent of the ball"). No "xG". Max 30 words.
- analyst: wants the detail. "xG", "progressive passes", "territory" are welcome, with up to two
  numbers (xG to two decimals, possession as %). Max 35 words.
(N stands for the real number from the FACT lines: never copy a number from these instructions.)"""

WORD_LIMITS: dict[str, int] = {"beginner": 30, "fan": 30, "analyst": 35}


def fit_to_words(text: str, limit: int) -> str:
    """Keep whole sentences up to the word limit: a last-resort net, never cuts mid-sentence."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sentence in sentences:
        if kept and len(" ".join(kept + [sentence]).split()) > limit:
            break
        kept.append(sentence)
    return " ".join(kept)


def run_of_play(stats: StatsEngine) -> dict:
    """Who had the ball and who was dangerous in the last 10 minutes. They can be different teams:
    having the ball isn't the same as being on top."""
    possession = stats.possession(recent=True)
    ball = max(possession, key=possession.get)
    even = abs(possession[stats.home] - possession[stats.away]) < 10
    leader = stats.momentum()["leader"]
    return {
        "more_of_the_ball": "neither team, about even" if even else ball,
        "their_share_of_the_ball": None if even else f"{round(possession[ball])}%",
        "more_dangerous": leader or "neither team",
    }


def angle_for(moment: Moment, stats: StatsEngine) -> str:
    """Code picks the angle from what the ranker and the stats say; the model fills in the words.
    The angle must be true for this match: a model told "show who dominated" when the ball and the
    danger were with different teams gave one team's possession to the other to fit the story."""
    if moment.kind == "goal":
        if "against the run of play" in moment.reason:
            picture = run_of_play(stats)
            ball, danger = picture["more_of_the_ball"], picture["more_dangerous"]
            if ball not in (danger, "neither team, about even"):
                return (f"SPLIT: {ball} had more of the ball, but {danger} had been more dangerous. "
                        "Keep each fact with its team, and say how good the chance was.")
            return ("CONTRAST: the scoring team had NOT been on top: the other side had been the more "
                    "dangerous team. Say how good the chance was.")
        return "CONTEXT + QUALITY: was this goal coming (who had been on top), and how good was the chance?"
    if moment.kind == "chance":
        return "QUALITY: how good was the chance, and is this team pushing?"
    if moment.kind == "attack":
        return "RARITY: how unusual was this pass or run?"
    if moment.kind == "card":
        return ("PRESSURE: is the booked player's team under the cosh? Combine it with the "
                "minute and score from the input: what does the card mean for the rest of the match?")
    if moment.kind == "phase":
        return "SUMMARY: who has been the better side so far?"
    return "CONTEXT: what is the shape of the game right now?"


def concept_for(event: MatchEvent, moment: Moment, stats: StatsEngine) -> Concept | None:
    """The playbook concept that explains this moment, picked by code from what we know for sure."""
    card = event.foul.card if event.foul else event.card
    shot_type = event.shot.type if event.shot else None
    if card in ("Red Card", "Second Yellow"):
        return CONCEPTS["Playing with ten men"]
    if moment.kind in ("goal", "chance"):
        if event.play_pattern == "From Counter":
            return CONCEPTS["Counter-attack and transitions"]
        if event.play_pattern in ("From Corner", "From Free Kick") or shot_type in ("Penalty", "Free Kick"):
            return CONCEPTS["Set pieces"]
        if moment.kind == "goal" and "most-used side" in (stats.patterns.goal_route(event) or ""):
            return CONCEPTS["Attacking channels and overloads"]
        if moment.kind == "goal":
            picture = run_of_play(stats)
            if picture["more_of_the_ball"] not in (picture["more_dangerous"], "neither team, about even"):
                return CONCEPTS["Possession versus danger"]
            if event.minute >= 80:
                return CONCEPTS["Game state and the late game"]
            return None
        return CONCEPTS["Chance quality and expected goals"]
    if moment.kind == "attack" and event.pass_:
        if event.pass_.cross:
            return CONCEPTS["Crosses and cut-backs"]
        return CONCEPTS["Progressive and line-breaking passes"]
    return None


def momentum_words(stats: StatsEngine) -> dict[str, str]:
    """Who has been on top in the last 10 minutes, in words: a model handed "value -0.3" says it."""
    m = stats.momentum()
    if not m["leader"]:
        return {"on_top": "neither team", "how_clearly": "evenly matched"}
    strength = abs(m["value"])
    how = "dominating" if strength >= 0.6 else "clearly" if strength >= 0.35 else "slightly"
    return {"on_top": m["leader"], "how_clearly": how}


def tempo_word(stats: StatsEngine) -> str:
    label = stats.tempo()["label"]
    return {"chaotic": "scrappy"}.get(label, label)


def facts_for(event: MatchEvent, moment: Moment, stats: StatsEngine) -> dict[str, str]:
    """What the angle needs, gathered by code BEFORE the model is called: one model call instead of
    a round trip per tool. Grouped BY TEAM, so every number already sits next to its team: listed by
    topic ("ball: X 65%", "shots: X 1, Y 5"), the model re-paired them wrongly 3 times in 9."""
    possession = stats.possession(recent=True)
    shots = stats.recent_shots()
    momentum = momentum_words(stats)
    facts = {}
    for team in (stats.home, stats.away):
        line = f"{round(possession[team])}% of the ball, {shots[team]} shot{'s' * (shots[team] != 1)}"
        if momentum["on_top"] == team:
            line += f"; the more dangerous side ({momentum['how_clearly']})"
        facts[f"{team}, last 10 min"] = line
    if momentum["on_top"] == "neither team":
        facts["more dangerous, last 10 min"] = "neither team, evenly matched"
    for team in (stats.home, stats.away):
        if team in CLUB_BY_NAME:  # a league club: where it stands before today
            row = next(r for r in league().table() if r["team"] == team)
            facts[f"{team}, league before today"] = (
                f"{ordinal(row['position'])} of 20, {row['points']} points from {row['played']} games, "
                f"form {row['form'] or 'none'}")
    if event.is_goal and event.player and event.team in CLUB_BY_NAME:
        before = league().player_goals(event.player)
        facts[f"{event.player}, league goals before today"] = str(before)
    for team in (stats.home, stats.away):
        for i, pattern in enumerate(stats.patterns.patterns(team), 1):
            facts[f"{team}, pattern {i}"] = pattern
    if event.is_goal and (route := stats.patterns.goal_route(event)):
        facts[f"this goal's attack, by {event.team}"] = route
    if event.shot and (quality := stats.shot_quality(event)):
        xg = quality["xg"]
        facts[f"this shot, by {event.team}"] = (f"{quality['label']}: about {round(xg * 100)}% of shots like "
                                                f"it are scored (xG {xg:.2f})")
    if moment.kind == "attack" and (rarity := stats.pass_rarity(event)):
        facts[f"this pass, by {event.team}"] = (
            f"moved the ball {round(rarity['gain'] * METERS_PER_UNIT)} m towards goal; "
            f"{round(rarity['share_of_passes_this_good'] * 100)}% of this match's passes gained as much")
    if moment.kind == "phase":
        overall = stats.possession()
        for team in (stats.home, stats.away):
            facts[f"{team}, whole match"] = (f"{round(overall[team])}% of the ball, "
                                             f"{stats.shots[team]} shots, xG {stats.xg[team]:.2f}")
    if moment.kind not in ("goal", "chance", "attack", "phase"):
        facts["game feel"] = tempo_word(stats)
    return facts


def build_tools(stats: StatsEngine, events_by_id: dict[str, MatchEvent]) -> list:
    """The Analyst's tools: thin wrappers over the live stats engine. The model never runs them;
    it asks, the framework runs them here and sends back the result."""

    def get_score() -> dict:
        """The current score and minute."""
        return {"score": stats.score, "minute": stats.minute}

    def get_possession(recent: Annotated[bool, "True for the last 10 minutes only"] = False) -> dict:
        """Share of possession per team (%), for the whole match or the last 10 minutes."""
        return stats.possession(recent=recent)

    def get_run_of_play() -> dict:
        """The last 10 minutes in one call: which team had more of the ball (and its share) and which
        team was more dangerous. They can be different teams."""
        return {key: value for key, value in run_of_play(stats).items() if value is not None}

    # These two speak in words, not internal scales: a model handed "value -0.3" tends to say it,
    # whatever the instructions say. Don't give the model numbers you don't want spoken.
    def get_momentum() -> dict:
        """Who has been on top in the last 10 minutes, and how clearly."""
        return momentum_words(stats)

    def get_tempo() -> dict:
        """How the game feels right now: scrappy (ball changing hands a lot), balanced, or controlled."""
        return {"game_feel": tempo_word(stats)}

    def get_shots_and_xg() -> dict:
        """Shots and total expected goals (xG) per team so far."""
        return {"shots": stats.shots, "xg": stats.xg}

    def get_shot_quality(event_id: Annotated[str, "The id of a Shot event"]) -> dict:
        """Expected goals (xG) of a shot: how likely a shot like it is to score, 0-1, with a label."""
        event = events_by_id.get(event_id)
        return (stats.shot_quality(event) if event else None) or {"error": "not a shot"}

    def get_pass_rarity(event_id: Annotated[str, "The id of a Pass event"]) -> dict:
        """How far a pass moved the ball towards goal, and the share of this match's passes as good."""
        event = events_by_id.get(event_id)
        return (stats.pass_rarity(event) if event else None) or {"error": "not a pass"}

    return [get_score, get_possession, get_run_of_play, get_momentum, get_tempo, get_shots_and_xg,
            get_shot_quality, get_pass_rarity]


class Analyst:
    def __init__(self, stats: StatsEngine, events_by_id: dict[str, MatchEvent], use_model: bool) -> None:
        self.agent = Agent(
            chat_client(),
            name="analyst",
            instructions=INSTRUCTIONS,  # no tools: code hands it the FACTS (one call, not three)
            default_options={"temperature": 0.4, "max_tokens": 150},
        ) if use_model else None
        self.stats = stats

    async def analyse(self, event: MatchEvent, moment: Moment, viewer: ViewerProfile,
                      context: dict[str, str] | None = None, angle: str | None = None) -> str | None:
        """One or two sentences at the viewer's level; None without a model or when too slow.
        The pipeline can add context (the story so far, what she said earlier) and its own angle."""
        if not self.agent:
            return None
        context = context or {}
        angle = angle or angle_for(moment, self.stats)
        if event.is_goal and "most-used side" in (self.stats.patterns.goal_route(event) or ""):
            angle += " It came down their most-used side: connect the goal to that pattern."
        if "CALLBACK" in context:  # code wrote the opening, so the minute stays with the old remark
            angle += (" You flagged this earlier (YOU SAID EARLIER). Begin your line with CALLBACK exactly, "
                      "then connect this goal to it.")
        fields = event_fields(event, moment, self.stats) | {"ANGLE": angle, "VIEWER_LEVEL": viewer.level}
        if viewer.team in (self.stats.home, self.stats.away):
            fields["VIEWER_SUPPORTS"] = viewer.team
            if moment.kind in ("goal", "chance", "card", "phase"):  # code decides: say it to the fan
                good = (event.team == viewer.team) != (moment.kind == "card")
                fields["ANGLE"] += (f" Speak to the {viewer.team} fan: what this means for their club "
                                    f"({'good news' if good else 'a worry'}), using its league position "
                                    "from the FACT lines. Stay fair to the other team.")
        fields |= context
        facts = facts_for(event, moment, self.stats)
        fields |= {f"FACT {name}": fact for name, fact in facts.items()}
        if concept := concept_for(event, moment, self.stats):
            brief = concept.brief(viewer.level)
            fields |= {"TACTICS": f"{brief['concept']}: {brief['idea']}",
                       "TACTICS_EXAMPLE": brief["example_line_for_tone_only"],
                       "TACTICS_DO_NOT_CLAIM": brief["do_not_claim"]}
        allowed = numbers_in(*facts.values(), *context.values(), angle, str(event.minute))
        allowed |= self._one_in(event)
        try:
            return await asyncio.wait_for(self._write(as_text(fields), viewer.level, event, allowed),
                                          DEADLINE_SECONDS)
        except Exception as error:  # late or failed: silence beats a generic line
            log.warning("analyst stayed quiet: %s", type(error).__name__)
            return None

    def _one_in(self, event: MatchEvent) -> set[str]:
        """A beginner hears a 19% chance as "about 1 in 5": those numbers are allowed too."""
        quality = self.stats.shot_quality(event) if event.shot else None
        if not quality or quality["xg"] <= 0:
            return set()
        n = round(1 / quality["xg"])
        return {"1", *(str(k) for k in (n - 1, n, n + 1) if k > 1)}

    async def _write(self, prompt: str, level: str, event: MatchEvent, allowed: set[str]) -> str | None:
        text = await self._draft(prompt, level)
        if problems := check_line(text, event, self.stats, allowed):
            # One retry, told exactly what was wrong; if it's still wrong, silence beats a wrong fact.
            text = await self._draft(f"{prompt}\nYOUR LAST LINE: {text}\nWRONG: {'; '.join(problems)}.\n"
                                     "Write it again, keeping every fact with its team.", level)
            if problems := check_line(text, event, self.stats, allowed):
                log.warning("analyst line failed the check twice: %s", "; ".join(problems))
                return None
        return text

    async def _draft(self, prompt: str, level: str) -> str:
        text = (await self.agent.run(prompt)).text.strip()
        limit = WORD_LIMITS[level]
        if len(text.split()) > limit:  # the model doesn't count words: ask once to shorten
            text = (await self.agent.run(
                f"Rewrite in at most {limit} words for a {level} viewer. Keep the key insight and "
                f"every number exactly as it is. Text: {text}")).text.strip()
        return fit_to_words(text, limit + 5)
