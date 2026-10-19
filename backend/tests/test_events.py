"""Event model, StatsBomb adapter and match sources. Fixtures are fictional, in StatsBomb's format."""
import json
from pathlib import Path

import pytest

from app.events.adapters import statsbomb
from app.events.io import load_match_file, save_match_file
from app.match.demo import DEMO_MATCH
from app.match.sources import UnknownSource, load_source

FIXTURE = Path(__file__).parent / "fixtures" / "statsbomb_format_sample.json"


def adapted():
    return statsbomb.to_events(json.loads(FIXTURE.read_text()))


def test_adapter_drops_types_we_dont_use():
    types = [e.type for e in adapted()]
    assert "Starting XI" not in types and "Ball Receipt*" not in types
    assert types == ["Pass", "Shot", "Pass", "Card", "Foul Committed"]


def test_adapter_maps_pass_details_and_defaults_outcome_to_complete():
    first_pass = adapted()[0]
    assert first_pass.pass_.recipient == "M. Ferro"
    assert first_pass.pass_.technique == "Through Ball"
    assert first_pass.pass_.outcome == "Complete"  # StatsBomb omits it on completed passes
    assert first_pass.under_pressure and first_pass.play_pattern == "From Counter"
    assert adapted()[2].pass_.outcome == "Incomplete"


def test_adapter_maps_shot_card_and_foul():
    events = adapted()
    shot = events[1]
    assert shot.is_goal and shot.shot.first_time and shot.shot.provider_xg == 0.2
    assert events[3].type == "Card" and events[3].card == "Yellow Card"
    assert events[4].foul.advantage


def test_match_file_round_trip(tmp_path):
    path = tmp_path / "match.json"
    save_match_file(DEMO_MATCH, path)
    assert "\"pass\"" in path.read_text()  # written with StatsBomb's field name, not pass_
    assert load_match_file(path) == DEMO_MATCH


def test_sources():
    assert load_source("demo") is DEMO_MATCH
    assert load_source("synthetic:sample_match") == DEMO_MATCH  # the committed example file
    for bad in ("../secret", "synthetic:../../etc", "statsbomb:does-not-exist", "nope:1"):
        with pytest.raises(UnknownSource):
            load_source(bad)
