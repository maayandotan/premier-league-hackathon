"""Tactical patterns from event locations and timing (#48): the Tactical Intelligence Engine.

Plain code over the event feed, like the rest of the stats engine. Over the last 15 minutes, per
team, it counts:

- final-third entries by channel (left / centre / right, from the attacking team's view)
- transitions: the ball won, then a shot or a box entry within 12 seconds in the same possession
- ball wins in the opponent's half (how high a team presses)
- crosses, and how many led to a shot
- field tilt: each team's share of the passes played in the final third

A pattern is only claimed once there's enough of it (the thresholds below). They're our own
heuristics, not official definitions; event data can't see positions, shape or off-ball runs,
so nothing here claims those.
"""
from collections import Counter, deque
from dataclasses import dataclass

from app.events.models import MatchEvent
from app.stats.geometry import in_box, in_final_third

WINDOW_SECONDS = 15 * 60
WINDOW_WORDS = "in the last 15 minutes"
TRANSITION_SECONDS = 12
BALL_WINS = {"Ball Recovery", "Interception"}

# When a pattern is worth saying out loud.
# Calibrated on generated matches with no tactics in them: there these fire rarely, so a pattern
# that does show up is really there (random data always looks like something at low bars).
MIN_ENTRIES, MIN_CHANNEL_SHARE = 6, 0.6
MIN_TRANSITIONS = 3
MIN_HIGH_WINS, HIGH_WINS_RATIO = 6, 2.0
MIN_CROSSES, MAX_CROSS_SHOTS = 7, 1
MIN_FINAL_THIRD_PASSES, MIN_TILT = 15, 0.75


def channel(y: float) -> str:
    """The attacking team's left, centre or right (y 0 is its left touchline)."""
    return "left" if y < 80 / 3 else "right" if y > 160 / 3 else "centre"


@dataclass(frozen=True)
class _Mark:
    seconds: int
    team: str
    kind: str  # entry | win_high | win_low | transition | cross | cross_shot | f3_pass
    detail: str | None = None  # the channel, for entries


class PatternTracker:
    def __init__(self, home: str, away: str) -> None:
        self.home, self.away = home, away
        self.now = 0
        self._marks: deque[_Mark] = deque()
        self._last_win: dict[str, tuple[int, int | None]] = {}  # team -> (seconds, possession)
        self._last_cross: dict[str, tuple[int, int | None]] = {}
        self._transitions_counted: set[int | None] = set()
        self._possession_channel: dict[int | None, str] = {}  # possession id -> where it entered
        self._match_channels = {home: Counter(), away: Counter()}  # all match, not just the window

    # ---------- feeding events ----------

    def update(self, event: MatchEvent) -> None:
        self.now = max(self.now, event.match_seconds)
        team, seconds = event.team, event.match_seconds
        if team not in (self.home, self.away) or event.location is None or event.period == 5:
            return
        x, y = event.location[:2]

        if event.type in BALL_WINS or (event.type == "Duel" and event.outcome == "Won"):
            self._mark(seconds, team, "win_high" if x >= 60 else "win_low")
            self._last_win[team] = (seconds, event.possession)

        end = None
        if event.pass_ is not None and event.pass_.outcome == "Complete":
            end = event.pass_.end_location
        elif event.carry is not None:
            end = event.carry.end_location
        if end is not None and not in_final_third(x) and in_final_third(end[0]):
            self._mark(seconds, team, "entry", channel(end[1]))
            self._possession_channel[event.possession] = channel(end[1])
            self._match_channels[team][channel(end[1])] += 1
        if event.pass_ is not None and in_final_third(x):
            self._mark(seconds, team, "f3_pass")
        if event.pass_ is not None and event.pass_.cross:
            self._mark(seconds, team, "cross")
            self._last_cross[team] = (seconds, event.possession)

        box_entry = end is not None and in_box(*end[:2]) and not in_box(x, y)
        if event.shot is not None or box_entry:
            won = self._last_win.get(team)
            if (won and won[1] == event.possession and seconds - won[0] <= TRANSITION_SECONDS
                    and event.possession not in self._transitions_counted):
                self._transitions_counted.add(event.possession)
                self._mark(seconds, team, "transition")
        if event.shot is not None:
            crossed = self._last_cross.get(team)
            if crossed and crossed[1] == event.possession and seconds - crossed[0] <= 6:
                self._mark(seconds, team, "cross_shot")

        while self._marks and self._marks[0].seconds < self.now - WINDOW_SECONDS:
            self._marks.popleft()

    def _mark(self, seconds: int, team: str, kind: str, detail: str | None = None) -> None:
        self._marks.append(_Mark(seconds, team, kind, detail))

    # ---------- what they show ----------

    def counts(self, team: str) -> Counter:
        return Counter(m.kind for m in self._marks if m.team == team)

    def channels(self, team: str) -> Counter:
        return Counter(m.detail for m in self._marks if m.team == team and m.kind == "entry")

    def attack_channel(self, event: MatchEvent) -> str | None:
        """Where the attack an event belongs to entered the final third, if it did."""
        return self._possession_channel.get(event.possession)

    def goal_route(self, event: MatchEvent) -> str | None:
        """For a goal: the channel its attack came down, and how often the team has gone that way all
        match, so a goal can pay off a pattern ("down the right again: 24 of their 41 entries")."""
        route = self.attack_channel(event)
        tally = self._match_channels.get(event.team)
        if route is None or not tally or sum(tally.values()) < MIN_ENTRIES:
            return None
        n, total = tally[route], sum(tally.values())
        main = tally.most_common(1)[0][0]
        usual = "their most-used side" if route == main and n / total >= 0.45 else "not their usual side"
        return f"came down the {route}, {usual}: {n} of their {total} final-third entries this match"

    def main_channel(self, team: str) -> tuple[str, int, int] | None:
        """The channel a team keeps using, if it's a pattern: (channel, entries there, all entries)."""
        by_channel = self.channels(team)
        total = sum(by_channel.values())
        if total < MIN_ENTRIES:
            return None
        name, n = by_channel.most_common(1)[0]
        return (name, n, total) if n / total >= MIN_CHANNEL_SHARE else None

    def patterns(self, team: str) -> list[str]:
        """The patterns worth saying for a team, in words with the numbers behind them."""
        other = self.away if team == self.home else self.home
        mine, theirs = self.counts(team), self.counts(other)
        found = []
        if main := self.main_channel(team):
            name, n, total = main
            found.append(f"{n} of {total} final-third entries down the {name} {WINDOW_WORDS}")
        if mine["transition"] >= MIN_TRANSITIONS:
            found.append(f"{mine['transition']} quick attacks straight after winning the ball {WINDOW_WORDS}")
        presses = mine["win_high"] >= HIGH_WINS_RATIO * max(1, theirs["win_high"])
        if mine["win_high"] >= MIN_HIGH_WINS and presses:
            found.append(f"won the ball {mine['win_high']} times in the opponent's half {WINDOW_WORDS} "
                         f"({theirs['win_high']} for {other})")
        if mine["cross"] >= MIN_CROSSES and mine["cross_shot"] <= MAX_CROSS_SHOTS:
            found.append(f"{mine['cross']} crosses {WINDOW_WORDS}, {mine['cross_shot']} led to a shot")
        f3_total = mine["f3_pass"] + theirs["f3_pass"]
        if mine["f3_pass"] >= MIN_FINAL_THIRD_PASSES and mine["f3_pass"] / max(1, f3_total) >= MIN_TILT:
            found.append(f"{round(100 * mine['f3_pass'] / f3_total)}% of the passes in the final third "
                         f"{WINDOW_WORDS}")
        return found

    def summary(self) -> dict:
        """For a tool: each team's patterns in the window (or plainly none), and where it has
        entered the final third all match (a habit can be clear over the match, not the last 15)."""
        return {team: {"last_15_minutes": self.patterns(team) or [f"no clear pattern {WINDOW_WORDS}"],
                       "final_third_entries_all_match": {side: self._match_channels[team][side]
                                                         for side in ("left", "centre", "right")}}
                for team in (self.home, self.away)}
