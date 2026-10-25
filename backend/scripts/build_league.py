"""Play the Meridian League's first matchdays and save them to data/synthetic/league/season.json.

Run from backend/ after changing the clubs, the squads or the generator:
  .venv/bin/python -m scripts.build_league
"""
import json

from app.league.season import SEASON_FILE, build_season


def main() -> None:
    season = build_season()
    SEASON_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEASON_FILE.write_text(json.dumps(season, indent=1) + "\n")
    goals = sum(r["home_goals"] + r["away_goals"] for r in season["results"])
    print(f"{len(season['results'])} matches, {goals} goals -> {SEASON_FILE}")


if __name__ == "__main__":
    main()
