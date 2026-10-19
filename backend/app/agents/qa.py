"""The Q&A agent (#18): answers the viewer's questions while the match keeps going.

Built step by step in spikes/agents/qa_step_a.py. What we learned:
- "That foul": the question carries ASKED_AT (the match clock when it was asked) and a tool
  returns the notable events just BEFORE it. It found the right moment every time.
- It can't see the video: it must never judge whether a decision was right ("the foul was
  clear" was an invention). "Did they deserve it?" is answered with data.
- The model takes the shortest path, so make that path complete: one get_match_picture tool
  with who's on top, possession, shots and xG together, instead of five small tools.
- Rules come from our own glossary (get_rule), not from the model's memory.
"""
import asyncio
import logging
from collections.abc import Sequence
from typing import Annotated

from agent_framework import Agent

from app.agents.analyst import build_tools as stats_tools
from app.agents.client import chat_client
from app.agents.describe import event_fields
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

log = logging.getLogger(__name__)

DEADLINE_SECONDS = 12.0
MAX_QUESTION_CHARS = 200
UNAVAILABLE = "Sorry, I can't take questions right now. Keep watching!"

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

INSTRUCTIONS = """You answer a viewer's question during a live football broadcast, in the analyst's voice.

- If ASKED_AT says full time, the match is over: questions are about the whole match. For "the key
  moment", "the turning point" or "the best chance", call get_key_moments.
- The question was asked at ASKED_AT (match clock). If it refers to "that", "this" or "just now",
  call get_events_before to see what happened right before, and pick the moment that fits.
- For a question about a rule or a football term, call get_rule and explain it in your own words,
  applied to this moment if there is one.
- For anything about how the match is going, call get_match_picture: it has who's on top,
  possession, shots and xG together. No claims beyond what it returns: no "likely", no guessing.
- Every number comes from a tool. Don't invent details that the events don't show.
- You CANNOT SEE THE VIDEO. Never judge whether a decision was right, a foul was clear, or a
  player was unlucky. "Did they deserve it?" is answered with data: who had been on top and how
  good the chances were (get_match_picture, get_shot_quality for one shot).
- If you can't tell which moment they mean, say so briefly and answer about the most likely one.
- If the question isn't about this match or football, say kindly that you can only talk about the match.
- Answer in 2-3 short spoken sentences at VIEWER_LEVEL:
  beginner = everyday words, explain terms, at most one number said simply;
  fan = clear football language with a number or two, never the word "xG";
  analyst = precise terms and the numbers behind the answer (possession %, shots, xG).
- Never say tool names or internal scales."""


def build_qa_tools(stats: StatsEngine, timeline: Sequence[tuple[MatchEvent, Moment]],
                   events_by_id: dict[str, MatchEvent]) -> list:
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
            result.append({"clock": f"{event.minute}:{event.second:02d}", "event_id": event.id, **fields})
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
            result.append({"clock": f"{event.minute}:{event.second:02d}", "event_id": event.id, **fields})
        return result

    def get_rule(topic: Annotated[str, "A rule or football term, e.g. offside, penalty"]) -> dict:
        """A plain explanation of a football rule or term."""
        key = topic.lower().strip()
        for name, text in RULES.items():
            if name in key or key in name:
                return {"topic": name, "explanation": text}
        return {"error": f"no explanation for {topic!r}", "known_topics": list(RULES)}

    def get_match_picture() -> dict:
        """How the match is going: who is on top recently (in words), possession overall and in the
        last 10 minutes (%), shots and expected goals (xG) per team so far."""
        return {"on_top_recently": momentum["get_momentum"](), "possession": stats.possession(),
                "possession_last_10_min": stats.possession(recent=True),
                "shots": stats.shots, "xg": stats.xg}

    return [get_events_before, get_key_moments, get_rule, get_match_picture,
            momentum["get_shot_quality"], momentum["get_pass_rarity"]]


class QuestionAnswerer:
    def __init__(self, stats: StatsEngine, timeline: Sequence[tuple[MatchEvent, Moment]],
                 events_by_id: dict[str, MatchEvent], use_model: bool) -> None:
        self.agent = Agent(
            chat_client(),
            name="qa",
            instructions=INSTRUCTIONS,
            tools=build_qa_tools(stats, timeline, events_by_id),
            default_options={"temperature": 0.3, "max_tokens": 200},
        ) if use_model else None

    async def answer(self, question: str, minute: int, second: int, viewer: ViewerProfile,
                     full_time: bool = False) -> str:
        """A spoken answer. Never None: the viewer asked, so they always hear something."""
        if not self.agent:
            return UNAVAILABLE
        asked_at = "full time (the match is over)" if full_time else f"{minute}:{second:02d}"
        prompt = (f"QUESTION: {question[:MAX_QUESTION_CHARS]}\nASKED_AT: {asked_at}\n"
                  f"VIEWER_LEVEL: {viewer.level}")
        try:
            response = await asyncio.wait_for(self.agent.run(prompt), DEADLINE_SECONDS)
            return response.text.strip() or UNAVAILABLE
        except Exception as error:
            log.warning("Q&A failed: %s", type(error).__name__)
            return "Sorry, I couldn't work that one out in time. Ask me again in a moment!"
