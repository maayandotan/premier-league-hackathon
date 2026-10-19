"""Regenerate docs/event-schema.json and data/synthetic/sample_match.json from the models.

Run from backend/:  .venv/bin/python -m scripts.export_schema
"""
import json

from app.config import REPO_ROOT
from app.events.io import save_match_file
from app.events.models import Match
from app.match.demo import DEMO_MATCH


def main() -> None:
    schema_path = REPO_ROOT / "docs" / "event-schema.json"
    schema_path.write_text(json.dumps(Match.model_json_schema(by_alias=True), indent=2) + "\n")
    sample_path = REPO_ROOT / "data" / "synthetic" / "sample_match.json"
    save_match_file(DEMO_MATCH, sample_path)
    print(f"wrote {schema_path.relative_to(REPO_ROOT)} and {sample_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
