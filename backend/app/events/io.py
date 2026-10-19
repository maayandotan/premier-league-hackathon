"""Read and write matches in our own format (what the synthetic generator outputs)."""
from pathlib import Path

from app.events.models import Match


def load_match_file(path: Path) -> Match:
    return Match.model_validate_json(path.read_text())


def save_match_file(match: Match, path: Path) -> None:
    path.write_text(match.model_dump_json(by_alias=True, exclude_none=True, indent=2) + "\n")
