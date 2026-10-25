"""Statistics engine: plain code, no AI. It keeps live match state and computes the
numbers the agents explain. Every public method returns JSON-friendly data so it
can be exposed to the agents as a tool.
"""
from collections import deque

from app.events.models import MatchEvent
from app.stats.geometry import distance_to_goal, in_box, in_final_third
from app.stats.patterns import PatternTracker
from app.stats.xg import shot_xg

WINDOW_SECONDS = 10 * 60  # "recently" = the last 10 minutes of match time
TEMPO_WINDOW_SECONDS = 5 * 60
PROGRESSIVE_RATIO = 0.75  # a pass is progressive if it ends at least 25% closer to goal


def pass_progression(event: MatchEvent) -> dict | None:
    """How much a pass moved the ball towards goal, or None if it isn't a located pass."""
    if event.pass_ is None or event.location is None or event.pass_.end_location is None:
        return None
    start = distance_to_goal(*event.location[:2])
    end = distance_to_goal(*event.pass_.end_location[:2])
    return {
        "gain": round(start - end, 1),  # pitch units gained towards goal
        "progressive": end <= start * PROGRESSIVE_RATIO and event.pass_.outcome == "Complete",
        "into_box": in_box(*event.pass_.end_location[:2]) and not in_box(*event.location[:2]),
    }


def _threat(event: MatchEvent) -> float:
    """Rough attacking threat of one event, used for momentum."""
    if event.shot is not None:
        return 1.0 + 5 * (shot_xg(event) or 0)
    if event.location is None:
        return 0.0
    x, y = event.location[:2]
    if event.type in ("Pass", "Carry") and in_box(x, y):
        return 0.5
    if event.type in ("Pass", "Carry", "Dribble") and in_final_third(x):
        return 0.15
    return 0.0


class StatsEngine:
    def __init__(self, home: str, away: str) -> None:
        self.home, self.away = home, away
        self.score = {home: 0, away: 0}
        self.shootout = {home: 0, away: 0}
        self.shots = {home: 0, away: 0}
        self.xg = {home: 0.0, away: 0.0}
        self.passes = {home: 0, away: 0}
        self.progressive_passes = {home: 0, away: 0}
        self.cards: list[dict] = []
        self.clock = 0  # match seconds of the latest event
        self.minute = 0
        self._recent: deque[tuple[int, str, str, float]] = deque()  # (seconds, team, type, threat)
        self._possessions: deque[tuple[int, int]] = deque()  # (seconds, possession id) changes
        self._last_possession: int | None = None
        self._pass_gains: list[float] = []
        self.patterns = PatternTracker(home, away)  # tactical patterns (#48)

    # ---------- feeding events ----------

    def update(self, event: MatchEvent) -> None:
        self.clock, self.minute = max(self.clock, event.match_seconds), event.minute
        self.patterns.update(event)
        team = event.team
        if team not in self.score:  # unknown team name: ignore rather than crash mid-match
            return
        if event.shot is not None:
            if event.period == 5:
                self.shootout[team] += event.is_goal
            else:
                self.shots[team] += 1
                self.xg[team] = round(self.xg[team] + (shot_xg(event) or 0), 3)
                self.score[team] += event.is_goal
        if event.pass_ is not None and event.period < 5:
            self.passes[team] += 1
            if (prog := pass_progression(event)) is not None:
                self._pass_gains.append(prog["gain"])
                self.progressive_passes[team] += prog["progressive"]
        card = event.card or (event.foul.card if event.foul else None)
        if card:
            self.cards.append({"team": team, "player": event.player, "card": card, "minute": event.minute})
        if event.possession is not None and event.possession != self._last_possession:
            self._possessions.append((event.match_seconds, event.possession))
            self._last_possession = event.possession

        self._recent.append((event.match_seconds, team, event.type, _threat(event)))
        while self._recent and self._recent[0][0] < self.clock - WINDOW_SECONDS:
            self._recent.popleft()
        while self._possessions and self._possessions[0][0] < self.clock - TEMPO_WINDOW_SECONDS:
            self._possessions.popleft()

    # ---------- tools for the agents ----------

    def possession(self, recent: bool = False) -> dict[str, float]:
        """Share of passes per team, overall or in the last 10 minutes (a standard possession proxy)."""
        if recent:
            counts = {self.home: 0, self.away: 0}
            for _, team, type_, _ in self._recent:
                if type_ == "Pass":
                    counts[team] += 1
        else:
            counts = self.passes
        total = sum(counts.values())
        if not total:
            return {self.home: 50.0, self.away: 50.0}
        return {team: round(100 * n / total, 1) for team, n in counts.items()}

    def recent_shots(self) -> dict[str, int]:
        """Shots per team in the last 10 minutes."""
        counts = {self.home: 0, self.away: 0}
        for _, team, type_, _ in self._recent:
            if type_ == "Shot":
                counts[team] += 1
        return counts

    def momentum(self) -> dict:
        """Who is on top in the last 10 minutes: -1 (away dominating) to +1 (home dominating)."""
        threat = {self.home: 0.0, self.away: 0.0}
        for seconds, team, _, value in self._recent:
            age = (self.clock - seconds) / WINDOW_SECONDS
            threat[team] += value * (1 - 0.5 * age)  # recent events count more
        total = sum(threat.values())
        value = 0.0 if total == 0 else (threat[self.home] - threat[self.away]) / total
        leader = None if abs(value) < 0.2 else (self.home if value > 0 else self.away)
        return {"value": round(value, 2), "leader": leader,
                "threat": {t: round(v, 2) for t, v in threat.items()}}

    def tempo(self) -> dict:
        """Control vs chaos: possession changes per minute over the last 5 minutes."""
        minutes = max(1.0, min(TEMPO_WINDOW_SECONDS, self.clock) / 60)
        changes = len(self._possessions) / minutes
        label = "chaotic" if changes > 2.5 else "controlled" if changes < 1.2 else "balanced"
        return {"possession_changes_per_min": round(changes, 2), "label": label}

    def pass_rarity(self, event: MatchEvent) -> dict | None:
        """How unusual a pass's progression is: the share of this match's passes that gained as much."""
        prog = pass_progression(event)
        if prog is None or not self._pass_gains:
            return None
        share = sum(g >= prog["gain"] for g in self._pass_gains) / len(self._pass_gains)
        return {**prog, "share_of_passes_this_good": round(share, 3)}

    def shot_quality(self, event: MatchEvent) -> dict | None:
        """xG of a shot and what it means in words."""
        xg = shot_xg(event)
        if xg is None:
            return None
        label = "big chance" if xg >= 0.3 else "half chance" if xg >= 0.1 else "low-probability effort"
        return {"xg": xg, "label": label}

    def snapshot(self) -> dict:
        return {
            "minute": self.minute,
            "score": self.score,
            "shootout": self.shootout if any(self.shootout.values()) else None,
            "shots": self.shots,
            "xg": self.xg,
            "possession": self.possession(),
            "possession_last_10": self.possession(recent=True),
            "momentum": self.momentum(),
            "tempo": self.tempo(),
            "progressive_passes": self.progressive_passes,
            "cards": self.cards,
        }
