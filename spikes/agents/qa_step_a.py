"""Q&A, Step A: answering the viewer's questions mid-match.

What's different from the Analyst:
- "That foul": the question carries ASKED_AT (the match clock when the viewer asked), and a tool
  returns the notable events just BEFORE it, so the agent can work out which moment they mean.
- Football questions need rules, not numbers: get_rule() reads a small glossary we wrote.
- Any kind of question: about a moment, a rule, or the state of the match. The agent picks tools.

LOCAL ONLY with real data (DATA_POLICY.md). Run from the repo root:
  backend/.venv/bin/python spikes/agents/qa_step_a.py
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from agent_framework import Agent  # noqa: E402
from levels_step_b import tools_called  # noqa: E402

from app.agents.analyst import build_tools as stats_tools  # noqa: E402
from app.agents.client import chat_client  # noqa: E402
from app.agents.describe import event_fields  # noqa: E402
from app.events.models import MatchEvent  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.ranker import Moment, rank  # noqa: E402

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
    "extra time": "If a knockout match is level after 90 minutes, two halves of 15 minutes are added.",
    "penalty shootout": "If it's still level after extra time, each team takes penalties in turn; "
                        "after five each, the team that scored more wins.",
    "expected goals": "Expected goals (xG) is how often a shot like this is scored, based on where it "
                      "was taken from and how. A 0.1 xG shot goes in about 1 time in 10.",
    "counter-attack": "A counter-attack is a fast attack straight after winning the ball back, before "
                      "the other team can get back into position.",
}

INSTRUCTIONS = """You answer a viewer's question during a live football broadcast, in the analyst's voice.

- The question was asked at ASKED_AT (match clock). If it refers to "that", "this" or "just now",
  call get_events_before to see what happened right before, and pick the moment that fits.
- For a question about a rule or a football term, call get_rule and explain it in your own words,
  applied to this moment if there is one.
- For a question about how the match is going, use the stats tools.
- Every number comes from a tool. Don't invent details that the events don't show.
- You CANNOT SEE THE VIDEO. Never judge whether a decision was right, a foul was clear, or a
  player was unlucky. "Did they deserve it?" is answered with data: who had been on top
  and how good the chances were: call get_match_picture (and get_shot_quality for one shot).
- For anything about how the match is going, call get_match_picture: it has who's on top,
  possession, shots and xG together. No claims beyond what it returns: no "likely", no guessing.
- If you can't tell which moment they mean, say so briefly and answer about the most likely one.
- Answer in 2-3 short spoken sentences at VIEWER_LEVEL:
  beginner = everyday words, explain terms, at most one number said simply;
  fan = clear football language with a number or two, never the word "xG";
  analyst = precise terms and the numbers behind the answer (possession %, shots, xG).
- Never say tool names or internal scales."""


def match_picture_tool(stats: StatsEngine):
    """One tool with the whole picture: the model takes the shortest path, so make it a complete one."""
    momentum = {t.__name__: t for t in stats_tools(stats, {})}["get_momentum"]

    def get_match_picture() -> dict:
        """How the match is going: who is on top recently (in words), possession overall and in the
        last 10 minutes (%), shots and expected goals (xG) per team so far."""
        return {"on_top_recently": momentum(), "possession": stats.possession(),
                "possession_last_10_min": stats.possession(recent=True),
                "shots": stats.shots, "xg": stats.xg}

    return get_match_picture


def qa_tools(timeline: list[tuple[MatchEvent, Moment]]) -> list:
    def get_events_before(
        minute: Annotated[int, "Match minute the viewer asked at"],
        second: Annotated[int, "Match second the viewer asked at"],
        count: Annotated[int, "How many notable events to return"] = 5,
    ) -> list[dict]:
        """The notable events just before a moment in the match, newest last, in plain words."""
        asked = minute * 60 + second
        notable = [(e, m) for e, m in timeline if e.match_seconds <= asked and m.score >= 1]
        return [{"clock": f"{e.minute}:{e.second:02d}", **_brief(e, m)} for e, m in notable[-count:]]

    def get_rule(topic: Annotated[str, "A rule or football term, e.g. offside, penalty, yellow card"]) -> dict:
        """A plain explanation of a football rule or term."""
        key = topic.lower().strip()
        for name, text in RULES.items():
            if name in key or key in name:
                return {"topic": name, "explanation": text}
        return {"error": f"no explanation for {topic!r}", "known_topics": list(RULES)}

    return [get_events_before, get_rule]


def _brief(event: MatchEvent, moment: Moment) -> dict:
    stats = _brief.stats  # the stats engine as it was during the replay
    fields = event_fields(event, moment, stats)
    fields.pop("minute", None)
    fields.pop("score", None)
    return fields


# (asked at minute, second, level, question)
QUESTIONS = [
    (78, 20, "beginner", "Why was that a penalty?"),
    (79, 40, "fan", "Did they deserve that goal?"),
    (81, 30, "analyst", "Who's been the better team in the last few minutes?"),
    (86, 10, "beginner", "What happens if he gets another card?"),
]


async def main() -> None:
    match = load_source(sys.argv[1] if len(sys.argv) > 1 else "statsbomb:3869685")
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    _brief.stats = stats
    timeline: list[tuple[MatchEvent, Moment]] = []
    events_by_id = {e.id: e for e in match.events}
    qa = Agent(chat_client(), name="qa", instructions=INSTRUCTIONS,
               tools=qa_tools(timeline) + [match_picture_tool(stats)]
               + [t for t in stats_tools(stats, events_by_id) if t.__name__ in ("get_shot_quality", "get_pass_rarity")],
               default_options={"temperature": 0.3, "max_tokens": 200})
    questions = list(QUESTIONS)
    for event in match.events:
        momentum_before = stats.momentum()["value"]
        stats.update(event)
        timeline.append((event, rank(event, stats, momentum_before)))
        if not questions:
            break
        minute, second, level, question = questions[0]
        if event.match_seconds >= minute * 60 + second:
            questions.pop(0)
            prompt = f"QUESTION: {question}\nASKED_AT: {minute}:{second:02d}\nVIEWER_LEVEL: {level}"
            start = time.perf_counter()
            response = await qa.run(prompt)
            print(f"\n🎤 {minute}:{second:02d} [{level}] \"{question}\"  ({time.perf_counter() - start:.1f}s)")
            print(f"   tools: {', '.join(tools_called(response))}")
            print(f"   🧠 {response.text.strip()}")


if __name__ == "__main__":
    asyncio.run(main())
