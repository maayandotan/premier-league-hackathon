"""Pick which match to replay.

  demo                built-in moment (always available)
  synthetic:<name>    data/synthetic/<name>.json, our own format
  fixture:<HOM>-<AWY> one of today's Meridian League fixtures, generated (same fixture, same match)
  statsbomb:<id>      data/real/events_<id>.json, LOCAL TESTING ONLY (git-ignored, DATA_POLICY.md)
"""
import re

from app.config import REPO_ROOT, settings
from app.events.adapters import statsbomb
from app.events.io import load_match_file
from app.events.models import Match
from app.match.demo import DEMO_MATCH

SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"
REAL_DIR = REPO_ROOT / "data" / "real"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")  # no paths, so a source can't reach outside its folder


class UnknownSource(ValueError):
    pass


def load_source(source: str) -> Match:
    kind, _, name = source.partition(":")
    if kind == "demo" and not name:
        return DEMO_MATCH
    if not _SAFE_NAME.match(name):
        raise UnknownSource(f"bad source name: {source!r}")
    if kind == "synthetic":
        path = SYNTHETIC_DIR / f"{name}.json"
        if path.exists():
            return load_match_file(path)
    elif kind == "fixture":
        from app.league.season import CURRENT_ROUND, play, todays_fixture  # the league needs the generator

        if teams := todays_fixture(name):
            return play(CURRENT_ROUND, *teams)
    elif kind == "statsbomb":
        # Never on the deployed site (DATA_POLICY.md): real data is for local testing only.
        if settings.allow_real_data and (REAL_DIR / f"events_{name}.json").exists():
            return statsbomb.load_match(REAL_DIR, name)
    raise UnknownSource(f"no such match: {source!r}")
