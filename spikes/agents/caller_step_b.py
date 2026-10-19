"""Caller, Step B: structured input and output.

What's new compared to Step A:
- OUTPUT: `response_format` with a JSON Schema. With "strict": true the model can't return
  anything else. It only writes the text; it doesn't decide anything.
- EXCITEMENT is decided by code from the Moment Ranker's score (predictable, and it matches
  the voice and the crowd roar). The model is told the level and writes to fit it.
- INPUT is clear fields instead of a loose sentence, so it can't mix up who passed to whom.
- TEMPERATURE 0.5 instead of 0.9: less "creativity" with the facts.

Run from spikes/agents/:  python3 caller_step_b.py
"""
import json

from caller_step_a import call_model

SYSTEM = """You are the play-by-play caller in a live football broadcast.
Call what is happening right now, the way it sounds when spoken live:
short bursts, ellipses for build-up, exclamations for big moments.
Maximum 12 words.
Describe, don't explain: the analyst handles the "why".
Use only facts from the input fields, and keep who did what exactly as given.
No adjectives about the quality of a shot, pass or player unless the input says so.

The input gives an EXCITEMENT level. Match it:
0 = calm and conversational, no exclamation marks
1 = building: urgency, ellipses
2 = big moment: exclamations, the key word in capitals (e.g. GOAL)"""

CALLER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "caller_line",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
}


def excitement_for(score: int, kind: str) -> int:
    """Code decides, from the ranker: the voice style and crowd roar follow the same rule."""
    if score >= 9:
        return 2
    if score >= 4 and kind in ("chance", "attack", "set_piece"):
        return 1
    return 0


# Moments as the ranker and the event model would describe them (fictional, DATA_POLICY.md).
MOMENTS = [
    {"minute": 34, "score": "Northbridge FC 0 - 0 Westvale United", "event": "Foul Committed",
     "player": "K. Osei", "team": "Westvale United", "where": "midfield",
     "ranker": {"score": 1, "kind": "stoppage", "reason": "foul"}},
    {"minute": 61, "score": "Northbridge FC 1 - 1 Westvale United", "event": "Pass",
     "passer": "D. Arlo", "receiver": "M. Ferro", "team": "Northbridge FC", "pass_type": "through ball",
     "where": "into the box", "ranker": {"score": 4, "kind": "attack", "reason": "ball into the box"}},
    {"minute": 80, "score": "Northbridge FC 2 - 2 Westvale United (after the goal)", "event": "Shot",
     "player": "M. Ferro", "team": "Northbridge FC", "body_part": "left foot", "where": "edge of the box",
     "outcome": "Goal", "ranker": {"score": 10, "kind": "goal", "reason": "late equalizer"}},
]


def to_input(moment: dict) -> tuple[str, int]:
    ranker = moment["ranker"]
    excitement = excitement_for(ranker["score"], ranker["kind"])
    fields = {k: v for k, v in moment.items() if k != "ranker"}
    fields["moment"] = ranker["reason"]
    fields["EXCITEMENT"] = excitement
    return "\n".join(f"{key}: {value}" for key, value in fields.items()), excitement


def main() -> None:
    for moment in MOMENTS:
        user, excitement = to_input(moment)
        print(f"\n=== INPUT ===\n{user}")
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        for attempt in (1, 2):
            response, seconds = call_model(messages, response_format=CALLER_SCHEMA, temperature=0.5)
            text = json.loads(response["choices"][0]["message"]["content"])["text"]
            print(f"  -> [{excitement}] {text}   ({seconds:.2f}s, {len(text.split())} words)")


if __name__ == "__main__":
    main()
