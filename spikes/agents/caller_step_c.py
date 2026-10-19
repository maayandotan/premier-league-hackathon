"""Caller, Step C: a real passage of play, through the real pipeline pieces.

  match events -> Stats Engine -> Moment Ranker -> (score >= 3) -> Caller

What's new compared to Step B:
- The input fields are built from real MatchEvents, not written by hand, in plain words.
- The Caller gets its own last 3 lines, so it can keep continuity and avoid repeating itself.
- A 2-second DEADLINE: if the model is slow (or the network fails), code says a template line
  instead. A live broadcast never waits for the model.
- We check timing: does each line finish before the next called moment arrives?

LOCAL ONLY with real data (DATA_POLICY.md): nothing it prints goes into the repo.
Run from the repo root with the backend's Python:
  backend/.venv/bin/python spikes/agents/caller_step_c.py [source] [from_minute] [to_minute]
  e.g.  backend/.venv/bin/python spikes/agents/caller_step_c.py statsbomb:3869685 76 82
"""
import json
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as DeadlineMissed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.events.models import MatchEvent  # noqa: E402
from app.match.sources import load_source  # noqa: E402
from app.stats.engine import StatsEngine  # noqa: E402
from app.stats.geometry import in_box  # noqa: E402
from app.stats.ranker import Moment, rank  # noqa: E402
from caller_step_a import call_model  # noqa: E402
from caller_step_b import CALLER_SCHEMA, excitement_for  # noqa: E402
from caller_step_b import SYSTEM as STEP_B_SYSTEM  # noqa: E402

CALL_THRESHOLD = 3
DEADLINE_SECONDS = 2.0
WORDS_PER_SECOND = 2.8  # roughly how fast Guy speaks

SYSTEM = STEP_B_SYSTEM + """

You also get your own recent lines. Keep continuity with them (e.g. "Ferro again..."),
and never repeat a phrase you just used.
No filler: never add mood phrases like "tension rising", "pressure mounts" or
"game on the line". If there is little to say, say less."""

# Data terms -> words a commentator would use.
PLAIN = {
    "Throw-in": "throw-in", "Corner": "corner", "Free Kick": "free kick", "Goal Kick": "goal kick",
    "Kick Off": "kick-off", "High Pass": "long ball", "Low Pass": "low pass", "Ground Pass": None,
    "Through Ball": "through ball", "Inswinging": "inswinging", "Outswinging": "outswinging",
    "Penalty": "penalty", "Open Play": None, "Right Foot": "right foot", "Left Foot": "left foot",
    "Head": "header", "Goal": "goal", "Saved": "saved", "Off T": "off target", "Post": "hits the post",
    "Blocked": "blocked", "Wayward": "off target", "From Counter": "counter-attack",
    "From Corner": "from a corner", "From Free Kick": "from a free kick", "From Throw In": "from a throw-in",
    "Regular Play": None,
}


def plain(term: str | None) -> str | None:
    return PLAIN.get(term, term.lower()) if term else None


def template_line(event: MatchEvent, moment: Moment, stats: StatsEngine) -> str:
    """The fallback when the model misses the deadline: short, always correct, instant."""
    who = event.player or event.team
    if moment.kind == "goal":
        return f"GOAL! {who}! {stats.score[stats.home]}-{stats.score[stats.away]}!"
    if moment.reason == "penalty awarded":
        return f"Penalty to {stats.away if event.team == stats.home else stats.home}!"
    return f"{who}... {moment.reason.split(',')[0]}..."


def zone(event: MatchEvent) -> str | None:
    """Where on the pitch, in words, from the acting team's point of view."""
    if not event.location:
        return None
    x, y = event.location[:2]
    if in_box(x, y):
        return "in the box"
    return "final third" if x >= 80 else "midfield" if x >= 40 else "own half"


def to_fields(event: MatchEvent, moment: Moment, stats: StatsEngine, recent: deque) -> dict:
    home, away = stats.home, stats.away
    fields = {
        "minute": event.minute,
        "score": f"{home} {stats.score[home]} - {stats.score[away]} {away}",
        "event": event.type,
        "player": event.player,
        "team": event.team,
        "where": zone(event),
        "play_pattern": plain(event.play_pattern),
    }
    if event.pass_:
        fields |= {"passer": event.player, "receiver": event.pass_.recipient,
                   "pass_type": plain(event.pass_.technique or event.pass_.type or event.pass_.height)}
        fields.pop("player")
    if event.shot:
        fields |= {"shot_type": plain(event.shot.type), "body_part": plain(event.shot.body_part),
                   "outcome": plain(event.shot.outcome)}
    if event.card or (event.foul and event.foul.card):
        fields["card"] = event.card or event.foul.card
    fields["moment"] = moment.reason
    fields["EXCITEMENT"] = excitement_for(moment.score, moment.kind)
    fields["your recent lines"] = " | ".join(recent) if recent else None
    return {k: v for k, v in fields.items() if v is not None}


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "statsbomb:3869685"
    start, end = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (76, 82)
    match = load_source(source)
    stats = StatsEngine(match.info.home.name, match.info.away.name)
    recent: deque[str] = deque(maxlen=3)
    busy_until = -1.0  # match second when the current line finishes being spoken
    late = fallbacks = 0
    pool = ThreadPoolExecutor(max_workers=4)

    print(f"{'clock':>6} {'rank':>4}  {'ex':>2}  line")
    for event in match.events:
        momentum_before = stats.momentum()["value"]
        stats.update(event)
        moment = rank(event, stats, momentum_before)
        if not (start <= event.minute < end) or moment.score < CALL_THRESHOLD:
            continue

        fields = to_fields(event, moment, stats, recent)
        user = "\n".join(f"{k}: {v}" for k, v in fields.items())
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        future = pool.submit(call_model, messages, response_format=CALLER_SCHEMA, temperature=0.5)
        try:
            response, seconds = future.result(timeout=DEADLINE_SECONDS)
            text = json.loads(response["choices"][0]["message"]["content"])["text"]
            source_tag = "model"
        except (DeadlineMissed, OSError) as error:  # too slow, or the network failed
            seconds = DEADLINE_SECONDS
            text = template_line(event, moment, stats)
            source_tag = f"TEMPLATE ({type(error).__name__})"
            fallbacks += 1
        recent.append(text)

        # Timing: the line can start when the model answers, and lasts words / speaking speed.
        starts_at = max(event.match_seconds + seconds, busy_until)
        delay = starts_at - event.match_seconds
        busy_until = starts_at + len(text.split()) / WORDS_PER_SECOND
        late += delay > 3
        flag = "  ⚠ late" if delay > 3 else ""
        clock = f"{event.minute}:{event.second:02d}"
        print(f"{clock:>6} {moment.score:>4}  {fields['EXCITEMENT']:>2}  {text}")
        print(f"{'':>15}↳ {moment.reason} · {source_tag} {seconds:.2f}s · heard {delay:.1f}s after{flag}")

    print(f"\nlines heard more than 3 s after their event: {late} · template fallbacks: {fallbacks}")
    pool.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
