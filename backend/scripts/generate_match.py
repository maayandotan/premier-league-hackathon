"""Generate synthetic matches into data/synthetic/ (#9).

Run from backend/:
  .venv/bin/python -m scripts.generate_match                         # every scenario, seed 1
  .venv/bin/python -m scripts.generate_match comeback --seed 7       # one scenario
  .venv/bin/python -m scripts.generate_match open --seed 3 --name open_3

Then replay one with ?source=synthetic:<name>. Scenarios: app/synthetic/scenarios.py.
"""
import argparse

from app.config import REPO_ROOT
from app.events.io import save_match_file
from app.synthetic.scenarios import SCENARIOS
from app.synthetic.simulator import generate_match

OUT_DIR = REPO_ROOT / "data" / "synthetic"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", nargs="?", choices=sorted(SCENARIOS), help="default: all of them")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--name", help="file name without .json (default: the scenario name)")
    args = parser.parse_args()
    for name in [args.scenario] if args.scenario else sorted(SCENARIOS):
        file_name = args.name or name
        match = generate_match(SCENARIOS[name], args.seed, match_id=file_name)
        save_match_file(match, OUT_DIR / f"{file_name}.json")
        goals = [f"{e.minute}' {e.player}" for e in match.events if e.is_goal]
        print(f"{file_name}: {len(match.events)} events, goals: {', '.join(goals) or 'none'}")


if __name__ == "__main__":
    main()
