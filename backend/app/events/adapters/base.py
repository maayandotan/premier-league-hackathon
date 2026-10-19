"""Adapters turn a data source's raw events into our MatchEvent model.

The agents only ever see MatchEvent, so a new source (a real provider feed later)
is just one more adapter. Planned adapters:
- synthetic: our generated matches (the only source in the submission)
- statsbomb: StatsBomb Open Data, for local testing only (see DATA_POLICY.md)
"""
from collections.abc import Iterable
from typing import Any, Protocol

from app.events.models import MatchEvent


class EventAdapter(Protocol):
    def to_events(self, raw: Iterable[dict[str, Any]]) -> list[MatchEvent]: ...
