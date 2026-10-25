"""Commentary in the viewer's language (English or Spanish).

How each voice gets to Spanish:
- Davis (caller) writes Spanish directly: he has no tools, nothing checks his lines, and he has
  ~2 s, so a second model call would not fit. His template fallbacks have Spanish versions.
- Roy (analyst), the recaps and Q&A still write English first, because the checker
  (checker.py) reads English: chance labels, "last 10 minutes", team attribution. Code checks the
  English line, then a translator turns the checked line into Spanish.
- The translation is checked too: the same numbers, the same team and player names. If it fails
  or is late, the viewer hears the checked English line (in the English voice) rather than a
  wrong Spanish one.
"""
import asyncio
import logging
import re

from agent_framework import Agent

from app.agents.client import chat_client

log = logging.getLogger(__name__)

LANGUAGES = ("en", "es")
DEADLINE_SECONDS = 3.0

INSTRUCTIONS = """You translate one line of live football commentary from English into Spanish
(neutral Latin American Spanish, the way a TV commentator or analyst says it on air).
Rules:
- Numbers written as digits stay exactly the same digits (N, N.N, a minute like N'). Numbers written
  as words stay words, in Spanish.
- Keep team names and player names exactly as written. Never translate them.
- Same meaning, same facts: add nothing, drop nothing.
- Usual Spanish football words: gol, penal, tiro de esquina, tiro libre, fuera de lugar,
  tarjeta amarilla, tarjeta roja, posesión, ocasión clara, goles esperados (xG), medio tiempo,
  final del partido, contragolpe, presión alta; "was fouled" is "recibió una falta".
Reply with the Spanish line only."""

# Lines code says itself (fallbacks), already in Spanish: no model needed.
FIXED = {
    "Sorry, I can't take questions right now. Keep watching!":
        "Perdón, ahora no puedo responder preguntas. ¡Sigue disfrutando del partido!",
    "I want to get that one right with the numbers. Give me a moment and ask me again!":
        "Quiero darte los números exactos. ¡Dame un momento y vuelve a preguntarme!",
    "Sorry, I couldn't work that one out in time. Ask me again in a moment!":
        "Perdón, no llegué a tiempo con esa. ¡Pregúntame otra vez en un momento!",
}

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers(text: str) -> list[str]:
    return sorted(n.replace(",", ".") for n in NUMBER.findall(text))


def check_translation(source: str, translated: str, names: list[str]) -> list[str]:
    """What the translation got wrong: a number or a name that changed. Empty means fine."""
    problems = []
    if numbers(source) != numbers(translated):
        problems.append(f"numbers changed: {numbers(source)} -> {numbers(translated)}")
    problems += [f"lost the name {name}" for name in names if name in source and name not in translated]
    return problems


class Translator:
    """English -> Spanish for lines that were already checked in English."""

    def __init__(self, use_model: bool, names: list[str] | None = None) -> None:
        self.names = names or []  # team and player names that must come through unchanged
        self.agent = Agent(chat_client(), name="translator", instructions=INSTRUCTIONS,
                           default_options={"temperature": 0, "max_tokens": 300}) if use_model else None

    async def to_spanish(self, text: str) -> str | None:
        """The Spanish line, or None (then the English line is used)."""
        if text in FIXED:
            return FIXED[text]
        if not self.agent:
            return None
        try:
            translated = (await asyncio.wait_for(self.agent.run(text), DEADLINE_SECONDS)).text.strip()
        except Exception as error:  # late or failed: the checked English line is better than nothing
            log.warning("translation failed: %s", type(error).__name__)
            return None
        if problems := check_translation(text, translated, self.names):
            log.warning("translation rejected: %s", "; ".join(problems))
            return None
        return translated
