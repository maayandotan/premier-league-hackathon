"""Stress test: several viewers watch full matches at once, asking questions and switching levels.

Plays every scenario at the same time against a running server, with the real agents and voices.
Each viewer asks a question right after every goal (the hardest moment: Davis, Roy, the roar and
the answer all at once) plus a few at random, and changes level mid-match. Then it reports, per
match: how fast Davis called moments, how often the template fallback was used, how many
questions got answers and how fast, the audio clips, and any errors.

Run from backend/ with the server running:
  .venv/bin/python -m scripts.stress_test                          # local, speed 20 (~5 min a match)
  .venv/bin/python -m scripts.stress_test --url wss://<live-host> --speed 10
"""
import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field

import websockets

QUESTIONS = ["Why was that a foul?", "Who has been better?", "What is offside?", "Was that a good chance?",
             "What just happened?", "How is the momentum?"]
LEVELS = ["beginner", "fan", "analyst"]


@dataclass
class Report:
    name: str
    events: int = 0
    goals: int = 0
    lines: dict[str, int] = field(default_factory=dict)  # "caller/model", "analyst/model", ...
    call_delays: list[float] = field(default_factory=list)  # seconds from event to Davis's line
    asked: dict[str, float] = field(default_factory=dict)  # question id -> time asked
    answer_delays: list[float] = field(default_factory=list)
    audio: int = 0
    errors: list[str] = field(default_factory=list)
    final_score: dict | None = None
    seconds: float = 0.0
    sample_answers: list[str] = field(default_factory=list)


async def watch(url: str, source: str, speed: float, level: str, seed: int, start: int = 0) -> Report:
    rng = random.Random(seed)
    report = Report(name=f"{source.split(':')[-1]} ({level})")
    started = time.monotonic()
    event_seen: dict[str, float] = {}
    pending_texts: list[str] = []
    query = f"source={source}&speed={speed}&level={level}&start={start}"
    question_rate = 0.02 if start else 0.004  # a short run asks more often, to still ask a few
    async with websockets.connect(f"{url}/ws/match?{query}", max_size=None) as ws:

        async def ask(text: str) -> None:
            pending_texts.append(text)
            await ws.send(json.dumps({"type": "question", "text": text}))

        level_switched = False
        async for raw in ws:
            message = json.loads(raw)
            kind = message["type"]
            now = time.monotonic()
            if kind == "event":
                report.events += 1
                event = message["event"]
                event_seen[event["id"]] = now
                if message["moment"]["kind"] == "goal":
                    report.goals += 1
                    await ask("Why was that goal important?")  # right on top of the goal
                elif rng.random() < question_rate:
                    await ask(rng.choice(QUESTIONS))
                if not level_switched and event["minute"] >= max(45, start + 5):
                    level_switched = True
                    await ws.send(json.dumps({"type": "set_level", "level": rng.choice(LEVELS)}))
            elif kind == "question":
                report.asked[message["id"]] = now
            elif kind == "commentary":
                line = message["line"]
                key = f"{line['speaker']}{'/answer' if line.get('reply_to') else ''}/{line['source']}"
                report.lines[key] = report.lines.get(key, 0) + 1
                if line.get("reply_to") in report.asked:
                    report.answer_delays.append(now - report.asked[line["reply_to"]])
                    if len(report.sample_answers) < 2:
                        report.sample_answers.append(line["text"])
                elif line["speaker"] == "caller" and line.get("event_id") in event_seen:
                    report.call_delays.append(now - event_seen[line["event_id"]])
            elif kind == "audio":
                report.audio += 1
            elif kind == "error":
                report.errors.append(message.get("message", "error"))
                break
            elif kind == "end":
                report.final_score = message["stats"]["score"]
                await ask("What was the key moment?")  # after full time
                end_time = time.monotonic()
                while time.monotonic() - end_time < 20 and len(report.answer_delays) < len(report.asked):
                    try:
                        raw = await asyncio.wait_for(ws.recv(), 20)
                    except (TimeoutError, websockets.ConnectionClosed):
                        break
                    message = json.loads(raw)
                    if message["type"] == "question":
                        report.asked[message["id"]] = time.monotonic()
                    if message["type"] == "commentary" and message["line"].get("reply_to") in report.asked:
                        line = message["line"]
                        report.answer_delays.append(time.monotonic() - report.asked[line["reply_to"]])
                        key = f"analyst/answer/{line['source']}"
                        report.lines[key] = report.lines.get(key, 0) + 1
                break
    report.seconds = time.monotonic() - started
    return report


def describe(delays: list[float]) -> str:
    if not delays:
        return "none"
    delays = sorted(delays)
    p95 = delays[min(len(delays) - 1, int(len(delays) * 0.95))]
    return f"n={len(delays)} median {statistics.median(delays):.1f}s p95 {p95:.1f}s max {delays[-1]:.1f}s"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="ws://localhost:8000")
    parser.add_argument("--speed", type=float, default=20)
    parser.add_argument("--start", type=int, default=0, help="start minute (earlier events still count)")
    parser.add_argument("--sources", default="synthetic:comeback,synthetic:red_card,synthetic:late_equaliser")
    args = parser.parse_args()
    sources = args.sources.split(",")
    print(f"{len(sources)} viewers at once, speed x{args.speed} from {args.start}', against {args.url}\n")
    reports = await asyncio.gather(*(watch(args.url, source, args.speed, LEVELS[i % 3], i, args.start)
                                     for i, source in enumerate(sources)), return_exceptions=True)
    for report in reports:
        if isinstance(report, BaseException):
            print(f"VIEWER CRASHED: {type(report).__name__}: {report}\n")
            continue
        answered = len(report.answer_delays)
        print(f"== {report.name}: {report.seconds / 60:.1f} min, {report.events} events, "
              f"{report.goals} goals, "
              f"final {report.final_score}")
        print(f"   lines: {dict(sorted(report.lines.items()))}, audio clips {report.audio}")
        print(f"   Davis after the event: {describe(report.call_delays)}")
        print(f"   questions answered {answered}/{len(report.asked)}: {describe(report.answer_delays)}")
        for text in report.sample_answers:
            print(f"     e.g. {text}")
        if report.errors:
            print(f"   ERRORS: {report.errors}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
