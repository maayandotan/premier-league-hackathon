"""The football tactics playbook (docs/football_tactics.md), split into sections the agents can use.

The doc is the single source: edit it and the agents follow. Code picks which concept fits a
moment or a question and hands the agent only that section, at the viewer's level: the idea,
one example line for tone, and what not to claim from event data.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import REPO_ROOT

PLAYBOOK = REPO_ROOT / "docs" / "football_tactics.md"

# Words a viewer (or the code) uses for each concept, in the order they're checked.
# Every concept in the playbook needs an entry here; a test checks the two match.
ALIASES: dict[str, tuple[str, ...]] = {
    "Playing with ten men": ("ten men", "10 men", "red card", "sent off", "down to ten"),
    "Counter-attack and transitions": ("counter", "transition", "on the break", "breakaway"),
    "Pressing and counter-pressing": ("press", "gegenpress", "win it back high", "high turnover"),
    "Possession versus danger": ("possession", "sterile", "dominat", "on top", "territory", "field tilt"),
    "Attacking channels and overloads": ("channel", "overload", "flank", "wing", "half-space", "switch"),
    "Build-up: playing out from the back versus going direct": (
        "build-up", "build up", "playing out", "play out", "long ball", "going long", "kick it long",
        "hoof", "direct", "goal kick"),
    "Progressive and line-breaking passes": ("progressive", "line-breaking", "line breaking", "through ball"),
    "Crosses and cut-backs": ("cross", "cut-back", "cutback", "cut back"),
    "Set pieces": ("set piece", "set-piece", "corner", "free kick", "throw-in", "throw in"),
    "Defending deep (the low block)": ("low block", "park the bus", "parking the bus", "sitting back",
                                       "sit back", "defending deep", "sit deep"),
    "Game state and the late game": ("game state", "chasing", "protect the lead", "protecting",
                                     "time-wasting", "time wasting", "late on", "late in the game"),
    "Chance quality and expected goals": ("xg", "expected goals", "chance quality", "big chance",
                                          "good chance", "should have scored", "how good was"),
}

LEVELS = ("beginner", "fan", "analyst")
NOT_MEASURED = ("Nothing yet: our match data doesn't measure this. Explain the idea, but don't say "
                "whether either team is doing it.")


@dataclass(frozen=True)
class Concept:
    name: str
    idea: str
    examples: dict[str, str]  # viewer level -> one example line (tone only; its numbers are made up)
    do_not_claim: str
    measured: str  # what our stats measure for it today; "" if nothing yet (a planned detector)

    def brief(self, level: str) -> dict[str, str]:
        """What an agent gets: the idea, what we can measure, one example at this level, the limits.
        Without "what we measure", a model asked "are they pressing?" used possession as proof."""
        return {"concept": self.name, "idea": self.idea,
                "what_we_measure_in_this_match": self.measured or NOT_MEASURED,
                "example_line_for_tone_only": self.examples.get(level, self.examples["fan"]),
                "do_not_claim": self.do_not_claim}


def _plain(text: str) -> str:
    """Markdown to plain text: no bold, no links, one line."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return " ".join(text.replace("**", "").replace("`", "").split())


def _part(block: str, label: str) -> str:
    match = re.search(rf"\*\*{re.escape(label)}\*\*\s*(.*?)(?=\n\n\*\*|\Z)", block, re.S)
    if not match:
        raise ValueError(f"playbook section is missing '{label}': {block.splitlines()[0]}")
    return match.group(1).strip()


def parse_playbook(text: str) -> tuple[dict[str, Concept], dict[str, str]]:
    """The concepts (between the two '---' lines) and the rules (the bullet list after them)."""
    _, concepts_text, rules_text = text.split("\n---\n")
    concepts = {}
    for block in re.split(r"^## ", concepts_text, flags=re.M)[1:]:
        name = block.splitlines()[0].strip()
        examples = {level.lower(): _plain(line).strip('"') for level, line in
                    re.findall(r"^- (Beginner|Fan|Analyst): (.+)$", _part(block, "Say it."), re.M)}
        in_our_data = _part(block, "In our data.")
        today = re.search(r"Today[^:]*:\s*(.*?)(?=\s*#48:|\Z)", in_our_data, re.S)
        concepts[name] = Concept(name=name, idea=_plain(_part(block, "What it is.")), examples=examples,
                                 do_not_claim=_plain(_part(block, "Don't claim.")),
                                 measured=_plain(today.group(1)) if today else "")
    rules = {}
    rules_section = rules_text.split("\n## Further reading")[0]
    for name, body in re.findall(r"^- \*\*(.+?)\.\*\* (.+)$", rules_section, re.M):
        rules[name.lower()] = _plain(body)
    return concepts, rules


def load_playbook(path: Path = PLAYBOOK) -> tuple[dict[str, Concept], dict[str, str]]:
    return parse_playbook(path.read_text())


CONCEPTS, PLAYBOOK_RULES = load_playbook()


def find_concept(topic: str) -> Concept | None:
    """The concept a question or topic is about, by the words people use for it."""
    words = topic.lower()
    for name, aliases in ALIASES.items():
        if any(alias in words for alias in aliases):
            return CONCEPTS[name]
    return None
