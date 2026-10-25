"""The Q&A agent (#18): answers the viewer's questions while the match keeps going.

Built step by step in spikes/agents/qa_step_a.py. What we learned:
- "That foul": the question carries ASKED_AT (the match clock when it was asked) and a tool
  returns the notable events just BEFORE it. It found the right moment every time.
- It can't see the video: it must never judge whether a decision was right ("the foul was
  clear" was an invention). "Did they deserve it?" is answered with data.
- The model takes the shortest path, so make that path complete: one get_match_picture tool
  with who's on top, possession, shots and xG together, instead of five small tools.
- Rules come from our own glossary (get_rule), not from the model's memory; tactics come from
  our playbook, docs/football_tactics.md (get_tactic).
"""
import asyncio
import logging
import re
from collections import deque
from collections.abc import Callable, Sequence
from typing import Annotated

from agent_framework import Agent

from app.agents.analyst import build_tools as stats_tools
from app.agents.analyst import fit_to_words
from app.agents.checker import check_answer, recorded, recording
from app.agents.client import chat_client
from app.agents.describe import event_fields, ordinal
from app.agents.tactics import CONCEPTS, LEVELS, PLAYBOOK_RULES, find_concept
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent
from app.league.clubs import CLUB_BY_NAME
from app.league.db import league
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment
from app.synthetic.squads import SQUADS, captain, find_player

log = logging.getLogger(__name__)

DEADLINE_SECONDS = 12.0
MAX_QUESTION_CHARS = 200
HISTORY = 6  # earlier questions and answers given with each new question, so "he" and "them" resolve
UNAVAILABLE = "Sorry, I can't take questions right now. Keep watching!"
NOT_SURE = "I want to get that one right with the numbers. Give me a moment and ask me again!"

# Our own plain-words explanations, so the agent explains rules from a source we control.
RULES = {
    "offside": "A player is offside if, when a teammate passes to them, they are nearer the opponent's "
               "goal line than both the ball and the second-last defender, in the opponent's half. "
               "The other team gets a free kick.",
    "penalty": "A penalty is given when a defender fouls an attacker (or handles the ball) inside their "
               "own penalty box. The attacking team gets one free shot from 11 metres with only the "
               "goalkeeper to beat.",
    "foul": "A foul is unfair contact or play: tripping, pushing, holding, or a reckless tackle. The "
            "other team gets a free kick, or a penalty if it happened in the fouling team's box.",
    "yellow card": "A yellow card is a caution for serious fouls, time-wasting or arguing. A second "
                   "yellow card in the same match means a red card.",
    "red card": "A red card sends the player off. Their team plays the rest of the match with one "
                "player fewer and cannot replace them.",
    "free kick": "After a foul, the fouled team restarts with a free kick from where it happened. Near "
                 "the goal it's a chance to shoot directly.",
    "corner": "A corner is given when the defending team puts the ball out over its own goal line. The "
              "attacking team kicks it in from the corner of the pitch.",
    "extra time": "If a knockout match is level after 90 minutes, two halves of 15 minutes are added.",
    "penalty shootout": "If it's still level after extra time, each team takes penalties in turn; "
                        "after five each, the team that scored more wins.",
    "expected goals": "Expected goals (xG) is how often a shot like this is scored, based on where it "
                      "was taken from and how. A 0.1 xG shot goes in about 1 time in 10.",
    "counter-attack": "A counter-attack is a fast attack straight after winning the ball back, before "
                      "the other team can get back into position.",
    "possession": "Possession is the share of the passes each team made: who has had the ball more.",
}
# The playbook's fuller versions win (e.g. offside: level is onside, and only if involved in play).
RULES |= {name: text for name, text in PLAYBOOK_RULES.items() if name != "yellow and red cards"}

INSTRUCTIONS = """You answer a viewer's question during a live football broadcast, in the analyst's voice.

- If ASKED_AT says full time, the match is over: questions are about the whole match. For "the key
  moment", "the turning point" or "the best chance", call get_key_moments.
- The question was asked at ASKED_AT (match clock). If it refers to "that", "this" or "just now",
  call get_events_before to see what happened right before, and pick the moment that fits.
- For a question about a rule or a football term, call get_rule and explain it in your own words,
  applied to this moment if there is one.
- For a question about tactics or how a team is playing (counter-attacks, pressing, possession,
  crosses, set pieces, sitting deep, playing with ten men...), call get_tactic with the
  VIEWER_LEVEL and explain the idea in your own words. Apply it to this match ONLY through what
  its what_we_measure_in_this_match says, with numbers from get_patterns and the other tools. If that says we
  don't measure it, explain the idea and say our match data can't show whether a team is doing
  it: never use other stats (like possession) as proof. Its example line shows tone only: never
  repeat its numbers or names. Never claim anything in its do_not_claim.
- For how good a chance was, find it with get_events_before, then call get_shot_quality with its
  event_id and use its label: "big chance" = great, "half chance" = decent, "low-probability
  effort" = hard. Never judge a chance without it.
- For "what did I miss?", a catch-up, or anything about earlier in the match, call get_match_story
  (and get_key_moments): tell it as a short story at VIEWER_LEVEL, in order.
- For the league (points, the table, form, a club's top scorer or captain, the season so far), call
  get_league_table or get_club_season. Say it's the table before today's match.
- For anything about how the match is going (including the score), call get_match_picture: it has
  the score, who's on top, possession, shots and xG together. No claims beyond what it returns:
  no "likely", no guessing.
- Every number comes from a tool. Don't invent details that the events don't show.
- You CANNOT SEE THE VIDEO. Never judge whether a decision was right, a foul was clear, or a
  player was unlucky. "Did they deserve it?" is answered with data: who had been on top and how
  good the chances were (get_match_picture, get_shot_quality for one shot).
- If you can't tell which moment they mean, say so briefly and answer about the most likely one.
- CONVERSATION SO FAR holds the viewer's earlier questions and your answers. Use it to understand who
  "he", "him", "that player", "they" or "the same team" mean; then answer the QUESTION with fresh
  tool calls (numbers may have changed since). A short follow-up that leaves out its subject
  continues the previous question: after "Is he the captain?", "who is then?" asks who the captain is.
  "He" or "him" is MOST_RECENT_PLAYER when it's given.
- For anything about a player (who he is, his goals and assists, his position, his match so far),
  call get_player.
- If VIEWER_SUPPORTS is given, the viewer is a fan of that club: "we", "us", "my team" and "our"
  mean that club (call get_club_season for it). Stay fair and accurate about both teams.
- If the question isn't about this match or football, say kindly that you can only talk about the match.
- Say when things happened the way the tools say it ("a moment ago", "in the 72nd minute").
  Never read out a clock time like "72:16" or ASKED_AT.
- Answer in 2-3 short spoken sentences, at most MAX_WORDS words, at VIEWER_LEVEL:
  beginner = everyday words, explain terms, at most one number said simply;
  fan = clear football language with a number or two, never the word "xG";
  analyst = precise terms and the numbers behind the answer (possession %, shots, xG).
- Never say tool names or internal scales."""


WORD_LIMITS: dict[str, int] = {"beginner": 40, "fan": 40, "analyst": 50}


def when(event: MatchEvent, asked: int | None = None) -> str:
    """When something happened, the way a commentator says it: never a clock like "72:16"."""
    if asked is not None and 0 <= asked - event.match_seconds < 90:
        return "a moment ago" if asked - event.match_seconds < 20 else "just before you asked"
    return f"in the {ordinal(event.minute)} minute"


def build_qa_tools(stats: StatsEngine, timeline: Sequence[tuple[MatchEvent, Moment]],
                   events_by_id: dict[str, MatchEvent], story: Callable[[], dict] | None = None) -> list:
    momentum = {t.__name__: t for t in stats_tools(stats, events_by_id)}

    def get_events_before(
        minute: Annotated[int, "Match minute the viewer asked at"],
        second: Annotated[int, "Match second the viewer asked at"],
        count: Annotated[int, "How many notable events to return"] = 5,
    ) -> list[dict]:
        """The notable events just before a moment in the match, newest last, in plain words."""
        asked = minute * 60 + second
        notable = [(e, m) for e, m in timeline if e.match_seconds <= asked and m.score >= 1]
        result = []
        for event, moment in notable[-max(1, min(count, 10)):]:
            fields = event_fields(event, moment, stats)
            fields.pop("score", None)
            fields.pop("minute", None)
            if event.is_goal and (route := stats.patterns.goal_route(event)):
                fields["attack_route"] = route
            result.append({"when": when(event, asked), "event_id": event.id, **fields})
        return result

    def get_key_moments(
        count: Annotated[int, "How many moments to return"] = 3,
    ) -> list[dict]:
        """The biggest moments of the match so far (goals, big chances, cards), biggest first,
        in plain words."""
        biggest = sorted(((e, m) for e, m in timeline if m.score >= 1), key=lambda em: -em[1].score)
        result = []
        for event, moment in biggest[:max(1, min(count, 5))]:
            fields = event_fields(event, moment, stats)
            fields.pop("score", None)
            fields.pop("minute", None)
            if event.is_goal and (route := stats.patterns.goal_route(event)):
                fields["attack_route"] = route
            result.append({"when": when(event), "event_id": event.id, **fields})
        return result

    def get_rule(topic: Annotated[str, "A rule or football term, e.g. offside, penalty"]) -> dict:
        """A plain explanation of a football rule or term."""
        key = topic.lower().strip()
        for name, text in RULES.items():
            if name in key or key in name:
                return {"topic": name, "explanation": text}
        return {"error": f"no explanation for {topic!r}", "known_topics": list(RULES)}

    def get_tactic(
        topic: Annotated[str, "The tactic or pattern asked about, e.g. counter-attack, pressing"],
        level: Annotated[str, "VIEWER_LEVEL: beginner, fan or analyst"] = "fan",
    ) -> dict:
        """Our playbook's explanation of a tactical idea: the idea, an example line for tone, and what
        event data can't show (so don't claim it)."""
        concept = find_concept(topic)
        if concept is None:
            return {"error": f"no playbook entry for {topic!r}", "known_topics": list(CONCEPTS)}
        return concept.brief(level if level in LEVELS else "fan")

    def get_patterns() -> dict:
        """Tactical patterns per team: in the last 15 minutes, in words with their counts (the side a
        team keeps attacking down, high pressing, quick attacks after winning the ball, crosses,
        territory; "no clear pattern" means there isn't one, so don't claim one), and the team's
        final-third entries by side over the whole match."""
        return stats.patterns.summary()

    def get_league_table() -> dict:
        """The Meridian League table BEFORE this match (it updates at full time): position, points,
        played, goal difference and form (last 5, oldest first) for every club, and the top scorers."""
        lg = league()
        keys = ("position", "team", "played", "points", "goal_difference", "form")
        return {"table": [{key: row[key] for key in keys} for row in lg.table()],
                "top_scorers": lg.top_scorers()}

    def get_player(name: Annotated[str, "A player's name or surname, e.g. Ferro or M. Ferro"]) -> dict:
        """One player: club, shirt number, position, captain or not, league goals and assists BEFORE
        this match, and what he has done in this match so far (goals, shots, cards, substitution)."""
        found = find_player(name, preferred=(stats.home, stats.away))
        if found is None:
            return {"error": f"no player called {name!r} in the league"}
        club, player = found
        this_match = {"goals": 0, "shots": 0, "cards": [], "substituted": None}
        for event, _ in timeline:
            if event.player == player.name:
                this_match["shots"] += event.shot is not None
                this_match["goals"] += event.is_goal
                if card := (event.foul.card if event.foul else event.card):
                    this_match["cards"].append(f"{card} in the {ordinal(event.minute)} minute")
                if event.substitution:
                    this_match["substituted"] = f"off in the {ordinal(event.minute)} minute"
            if event.substitution and event.substitution.replacement == player.name:
                this_match["substituted"] = f"came on in the {ordinal(event.minute)} minute"
        playing = club in (stats.home, stats.away)
        return {"name": player.name, "club": club, "number": player.number,
                "position": player.position if player.starter else f"substitute ({player.position})",
                "captain": captain(club) == player.name, "club_captain": captain(club),
                **league().player_season(player.name),
                "this_match": this_match if playing else "not playing in this match"}

    def get_club_season(team: Annotated[str, "A club's full name, e.g. Northbridge FC"]) -> dict:
        """A club's league season BEFORE this match: position, points, record, form, captain, its top
        scorers and assisters this season."""
        if team not in CLUB_BY_NAME:
            return {"error": f"no club called {team!r}", "clubs": list(CLUB_BY_NAME)}
        return league().club(team)

    def get_match_picture() -> dict:
        """How the match is going: the score and minute, who is on top recently (in words), possession
        overall and in the last 10 minutes (%), shots overall and in the last 10 minutes, and expected
        goals (xG) per team so far."""
        return {"score": stats.score, "minute": stats.minute,
                "on_top_recently": momentum["get_momentum"](), "possession": stats.possession(),
                "possession_last_10_min": stats.possession(recent=True),
                "shots_last_10_min": stats.recent_shots(),
                "shots": stats.shots, "xg": {team: round(xg, 2) for team, xg in stats.xg.items()}}

    def get_match_story() -> dict:
        """The story of the match so far and its latest logged moments (goals, red cards, big chances,
        patterns, what was said on air), with minutes. For catching up and anything about earlier."""
        return story() if story else {"story": "(no story yet)"}

    tools = [get_events_before, get_key_moments, get_rule, get_tactic, get_patterns, get_match_story,
             get_league_table, get_club_season, get_player, get_match_picture,
             momentum["get_shot_quality"], momentum["get_pass_rarity"]]
    return [recorded(tool) for tool in tools]  # so the answer can be checked against what they said


class QuestionAnswerer:
    def __init__(self, stats: StatsEngine, timeline: Sequence[tuple[MatchEvent, Moment]],
                 events_by_id: dict[str, MatchEvent], use_model: bool,
                 story: Callable[[], dict] | None = None) -> None:
        self.agent = Agent(
            chat_client(),
            name="qa",
            instructions=INSTRUCTIONS,
            tools=build_qa_tools(stats, timeline, events_by_id, story),
            default_options={"temperature": 0.3, "max_tokens": 200},
        ) if use_model else None
        self.stats = stats
        self.history: deque[tuple[str, str]] = deque(maxlen=HISTORY)  # what the viewer heard, in order
        self.recent_player: str | None = None  # who "he" means: found by code, not guessed by the model
        self._players = [p.name for team in (stats.home, stats.away) for p in SQUADS.get(team, [])]

    async def answer(self, question: str, minute: int, second: int, viewer: ViewerProfile,
                     full_time: bool = False) -> str:
        """A spoken answer. Never None: the viewer asked, so they always hear something."""
        if not self.agent:
            return UNAVAILABLE
        asked_at = "full time (the match is over)" if full_time else f"{minute}:{second:02d}"
        limit = WORD_LIMITS.get(viewer.level, WORD_LIMITS["fan"])
        prompt = (f"QUESTION: {question[:MAX_QUESTION_CHARS]}\nASKED_AT: {asked_at}\n"
                  f"VIEWER_LEVEL: {viewer.level}\nMAX_WORDS: {limit}")
        if viewer.team:
            prompt += f"\nVIEWER_SUPPORTS: {viewer.team}"
        if viewer.language != "en":  # the checker reads English; code translates the checked answer
            prompt += "\nANSWER_IN: English, even though the question may be in Spanish"
        if self.recent_player:
            prompt += (f"\nMOST_RECENT_PLAYER: {self.recent_player} (who \"he\" or \"him\" means, unless the "
                       "question names someone else)")
        if self.history:  # code keeps the conversation: only what the viewer actually heard
            prompt += "\nCONVERSATION SO FAR (oldest first):\n" + "\n".join(
                f"Viewer: {q}\nRoy: {a}" for q, a in self.history)
        said = {*re.findall(r"\b\d+(?:\.\d+)?\b", question), str(minute), str(second)}
        try:
            with recording() as tool_results:
                answer = await asyncio.wait_for(self._write(prompt, viewer.level, limit, tool_results, said),
                                                DEADLINE_SECONDS)
            if answer not in (NOT_SURE, UNAVAILABLE):
                self.history.append((question[:MAX_QUESTION_CHARS], answer))
                self.recent_player = self._last_player_named(question + " " + answer) or self.recent_player
            return answer
        except Exception as error:
            log.warning("Q&A failed: %s", type(error).__name__)
            return "Sorry, I couldn't work that one out in time. Ask me again in a moment!"

    def _last_player_named(self, text: str) -> str | None:
        """The player named last in a text ("M. Ferro" or just "Ferro"), from the two squads playing.
        The model kept reading "he" as the conversation's first player even when told otherwise."""
        found = {}
        for name in self._players:
            surname = name.split(". ")[-1]
            for match in re.finditer(rf"\b{re.escape(surname)}\b", text):
                found[name] = max(found.get(name, -1), match.start())
        return max(found, key=found.get) if found else None

    async def _write(self, prompt: str, level: str, limit: int, tool_results: list, said: set[str]) -> str:
        """Draft, check against what the tools returned, one retry if wrong, then an honest fallback
        (the viewer asked, so silence isn't an option; a wrong number is worse than "ask again")."""
        text = await self._draft(prompt, level, limit)
        if problems := check_answer(text, tool_results, self.stats, said):
            text = await self._draft(f"{prompt}\nYOUR LAST ANSWER: {text}\nWRONG: {'; '.join(problems)}.\n"
                                     "Answer again, with only numbers your tools gave, each with its team.",
                                     level, limit)
            if problems := check_answer(text, tool_results, self.stats, said):
                log.warning("Q&A answer failed the check twice: %s", "; ".join(problems))
                return NOT_SURE
        return text

    async def _draft(self, prompt: str, level: str, limit: int) -> str:
        text = (await self.agent.run(prompt)).text.strip()
        if len(text.split()) > limit * 1.2:  # the model doesn't count words: ask once to shorten
            text = (await self.agent.run(
                f"Rewrite this spoken answer in at most {limit} words for a {level} viewer. Keep the "
                f"answer to the question and every number exactly as it is. Text: {text}")).text.strip()
        return fit_to_words(text, limit + 10) or UNAVAILABLE
