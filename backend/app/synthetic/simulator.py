"""Synthetic match generator (#9): a possession-chain simulator.

A match is a series of possessions. Each starts from a restart (kick-off, throw-in, goal kick,
corner, free kick, penalty) or a turnover, and moves one action at a time (pass, carry, dribble,
cross, shot) until the ball is lost, goes out, a foul stops play, or someone shoots. What happens
next depends on where the ball is: deep in your own half you mostly keep it; near the box,
crosses and shots become likely.

Locations are in the attacking frame of the team on the ball, like StatsBomb: x 0 is its own
goal line, 120 the opponent's. When the ball changes team, the location flips.

The numbers are tuned with general football knowledge (about 25 shots, 2.7 goals, 22 fouls,
4 yellow cards and 10 corners a match), never with real data (DATA_POLICY.md rule 5).

A scenario (scenarios.py) can script the big moments. When a beat's minute comes, the
simulator plays a short sequence that leads to it, then carries on. In a scripted match only
the script scores goals, gives penalties and sends players off.
"""
import math
import random
from dataclasses import dataclass, field

from app.events.models import (
    CarryDetails,
    FoulDetails,
    Match,
    MatchEvent,
    MatchInfo,
    PassDetails,
    ShotDetails,
    SubstitutionDetails,
)
from app.stats.xg import shot_xg
from app.synthetic.scenarios import Beat, Scenario
from app.synthetic.squads import FORMATION_433, SQUADS, SquadPlayer, team_info

HALF_SECONDS = 45 * 60
GK = "Goalkeeper"
Point = tuple[float, float]


def in_box(x: float, y: float) -> bool:
    return x >= 102 and 18 <= y <= 62


def flip(point: Point) -> Point:
    """A location seen from the other team's side."""
    return round(120 - point[0], 1), round(80 - point[1], 1)


def clamp(x: float, y: float) -> Point:
    return round(min(119.5, max(0.5, x)), 1), round(min(79.5, max(0.5, y)), 1)


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class Side:
    name: str
    strength: float  # 0-1, nudges pass completion and finishing
    on_pitch: dict[str, SquadPlayer]  # position -> player; a substitute takes the position of who went off
    bench: list[SquadPlayer]
    sub_minutes: list[int]
    booked: set[str] = field(default_factory=set)
    came_on: set[str] = field(default_factory=set)  # substitutes are never taken off again


@dataclass
class Restart:
    kind: str  # kickoff | throw_in | goal_kick | corner | free_kick | penalty
    team: str
    location: Point  # in that team's frame


PATTERNS = {"kickoff": "From Kick Off", "throw_in": "From Throw In", "goal_kick": "From Goal Kick",
            "corner": "From Corner", "free_kick": "From Free Kick", "penalty": "Other"}


class MatchSimulator:
    def __init__(self, scenario: Scenario, seed: int, match_id: str | None = None) -> None:
        self.rng = random.Random(seed)
        self.scenario = scenario
        self.seed = seed
        self.match_id = match_id or f"{scenario.name}-{seed}"
        self.home, self.away = scenario.home, scenario.away
        self.sides = {
            scenario.home: self._side(scenario.home, scenario.home_strength),
            scenario.away: self._side(scenario.away, scenario.away_strength),
        }
        self.beats = sorted(scenario.beats, key=lambda b: b.minute)
        # Players the script needs keep their place until their moment.
        self.protected = {b.player for b in self.beats if b.player}
        self.events: list[MatchEvent] = []
        self.period = 1
        self.t = 0.0  # match clock in seconds; the second half starts again at 45:00
        self.poss_team = self.home
        self.poss_id = 0
        self.pattern = "From Kick Off"
        self.ball: Point = (60.0, 40.0)
        self.holder: str | None = None  # position of the player on the ball
        self.counter_steps = 0  # > 0 while a counter-attack is on
        self.last_pass: MatchEvent | None = None  # for assists
        self.restart: Restart | None = None

    def _side(self, name: str, strength: float) -> Side:
        squad = SQUADS[name]
        n_subs = self.rng.randint(3, 5)
        minutes = sorted(self.rng.randint(55, 86) for _ in range(n_subs))
        if self.rng.random() < 0.25:
            minutes[0] = 46  # a half-time change
        return Side(name=name, strength=strength,
                    on_pitch={p.position: p for p in squad if p.starter},
                    bench=[p for p in squad if not p.starter and p.line != "GK"],
                    sub_minutes=minutes)

    # ---------- the match ----------

    def run(self) -> Match:
        for period in (1, 2):
            self.period = period
            self.t = (period - 1) * HALF_SECONDS
            end = self.t + HALF_SECONDS + self._stoppage(period)
            for team in (self.home, self.away):
                self.emit("Half Start", team, duration=0, gap=0)
            self.restart = Restart("kickoff", self.home if period == 1 else self.away, (60.0, 40.0))
            while self.t < end:
                beat = self._due_beat()
                if self.restart:
                    self.do_restart()
                elif beat:
                    self.beats.remove(beat)
                    self.play_beat(beat)
                else:
                    self.step()
            self.restart = None
            for team in (self.home, self.away):
                self.emit("Half End", team, duration=0, gap=0)
        return Match(
            info=MatchInfo(
                id=self.match_id, home=team_info(self.home), away=team_info(self.away),
                competition="Synthetic League", source="synthetic",
                extra={"scenario": self.scenario.name, "seed": self.seed,
                       "description": self.scenario.description},
            ),
            events=self.events,
        )

    def _stoppage(self, period: int) -> int:
        minutes = self.rng.randint(1, 3) if period == 1 else self.rng.randint(3, 5)
        late_beats = [b.minute - 90 for b in self.beats if b.minute > 90]
        if period == 2 and late_beats:
            minutes = max(minutes, max(late_beats) + 1)  # leave time for a stoppage-time beat
        return minutes * 60 + self.rng.randint(0, 50)

    def _due_beat(self) -> Beat | None:
        if not self.beats:
            return None
        beat = self.beats[0]
        in_this_half = beat.minute <= 45 if self.period == 1 else beat.minute > 45
        return beat if in_this_half and self.t >= beat.minute * 60 else None

    # ---------- helpers ----------

    def other(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def near(self, team: str, point: Point, exclude: str | None = None, lines: tuple[str, ...] = ()) -> str:
        """A player likely to be near this point: their home spot moves up and down with the ball."""
        candidates = [pos for pos, p in self.sides[team].on_pitch.items()
                      if pos != exclude and (pos != GK or point[0] < 25) and (not lines or p.line in lines)]
        if not candidates:
            candidates = [pos for pos in self.sides[team].on_pitch if pos not in (exclude, GK)]
        shift = (point[0] - 60) * 0.4

        def weight(pos: str) -> float:
            hx, hy, _ = FORMATION_433[pos]
            spot = (hx if pos == GK else hx + shift, hy)
            return math.exp(-distance(spot, point) / 14)

        return self.rng.choices(candidates, [weight(pos) for pos in candidates])[0]

    def position_of(self, team: str, name: str | None) -> str | None:
        return next((pos for pos, p in self.sides[team].on_pitch.items() if p.name == name), None)

    def name_of(self, team: str, pos: str | None) -> str | None:
        player = self.sides[team].on_pitch.get(pos) if pos else None
        return player.name if player else None

    def emit(self, type_: str, team: str, pos: str | None = None, location: Point | None = None,
             duration: float = 1.0, gap: float | None = None, **fields) -> MatchEvent:
        seconds = int(self.t)
        event = MatchEvent(
            id=f"{self.match_id}-{len(self.events) + 1}", index=len(self.events) + 1, period=self.period,
            minute=seconds // 60, second=seconds % 60, type=type_, team=team,
            player=self.name_of(team, pos), position=pos, location=location,
            play_pattern=self.pattern, possession=self.poss_id, possession_team=self.poss_team,
            duration=round(duration, 2), **fields,
        )
        self.events.append(event)
        self.t += duration + (gap if gap is not None else self.rng.uniform(1.1, 3.1))
        return event

    def take_over(self, team: str, location: Point, holder: str | None = None,
                  pattern: str = "Regular Play") -> None:
        """The ball changes team (location in the new team's frame)."""
        if team != self.poss_team:
            self.poss_id += 1
        self.poss_team, self.ball, self.holder, self.pattern = team, clamp(*location), holder, pattern
        self.counter_steps = 0
        self.last_pass = None

    def win_ball(self, team: str, location: Point, kind: str = "Ball Recovery") -> None:
        """`team` wins the ball at `location` (its own frame): maybe the start of a counter."""
        pos = self.near(team, location)
        counter = 28 <= location[0] <= 70 and self.rng.random() < 0.3
        self.take_over(team, location, pos, "From Counter" if counter else "Regular Play")
        extra = {"outcome": "Won"} if kind == "Interception" else {}
        self.emit(kind, team, pos, location, duration=0.3, **extra)
        if counter:
            self.counter_steps = 5

    def set_restart(self, kind: str, team: str, location: Point, dead_time: tuple[float, float]) -> None:
        self.t += self.rng.uniform(*dead_time)
        self.restart = Restart(kind, team, location)

    # ---------- one action on the ball ----------

    def step(self) -> None:
        team, (x, y) = self.poss_team, self.ball
        if self.holder is None or self.holder not in self.sides[team].on_pitch:
            self.holder = self.near(team, self.ball)
        if self.rng.random() < (0.038 if x > 80 else 0.021):
            self.foul(self.other(team))
            return
        strength = self.sides[team].strength
        p_shot = 0.4 + 0.2 * (strength - 0.5) if in_box(x, y) else 0.08 if x >= 84 and 24 <= y <= 56 else 0
        wide = x >= 94 and (y < 18 or y > 62)
        if self.rng.random() < p_shot:
            self.shoot()
        elif wide and self.rng.random() < 0.4:
            self.cross()
        elif x >= 70 and self.rng.random() < 0.06:
            self.dribble()
        elif self.rng.random() < 0.36:
            self.carry()
        else:
            self.pass_ball()
        if self.counter_steps:
            self.counter_steps -= 1

    def pass_target(self) -> tuple[Point, str | None, str | None]:
        """Where the next pass goes, plus its technique and height."""
        x, y = self.ball
        roll = self.rng.random()
        technique = height = None
        if self.counter_steps:
            dx = self.rng.gauss(16, 8)
        elif x < 40 and roll < 0.1:
            dx, height = self.rng.gauss(40, 8), "High Pass"
        elif 50 < x < 90 and roll < 0.07:
            dx, technique = self.rng.gauss(24, 6), "Through Ball"
        elif x < 40:
            dx = self.rng.gauss(7, 12)
        elif x < 85:
            dx = self.rng.gauss(5, 13)
        else:
            dx = self.rng.gauss(-2, 10)
        dy = self.rng.gauss(0, 16) + 0.15 * (40 - y)
        return clamp(x + dx, y + dy), technique, height

    def pass_success(self, start: Point, end: Point, technique: str | None, height: str | None) -> float:
        chance = 0.93 if end[0] < 45 else 0.86 if end[0] < 85 else 0.72
        chance -= 0.005 * max(0.0, distance(start, end) - 25)
        if technique == "Through Ball":
            chance = 0.5
        if height == "High Pass":
            chance = min(chance, 0.6)
        if in_box(*end):
            chance -= 0.1
        chance += 0.12 * (self.sides[self.poss_team].strength - 0.5) + (0.06 if self.counter_steps else 0)
        return min(0.97, max(0.2, chance))

    def pass_ball(self, target: Point | None = None, kind: str | None = None, technique: str | None = None,
                  height: str | None = None, cross: bool = False, success: float | None = None,
                  recipient: str | None = None, offside_ok: bool = True) -> bool:
        """One pass. Returns True if it reached a teammate (the ball and holder move with it)."""
        team, start, passer = self.poss_team, self.ball, self.holder
        if target is None:
            target, technique, height = self.pass_target()
        end = clamp(*target)
        if success is None:
            success = self.pass_success(start, end, technique, height)
        receiver = recipient or self.near(team, end, exclude=passer)
        forward = end[0] - start[0]
        offside = (offside_ok and kind is None and end[0] >= 92
                   and (technique == "Through Ball" or forward > 15) and self.rng.random() < 0.07)
        near_line = end[1] <= 2 or end[1] >= 78 or end[0] >= 119
        if offside:
            outcome = "Pass Offside"
        elif self.rng.random() < success:
            outcome = "Complete"
        else:
            outcome = "Out" if near_line or self.rng.random() < 0.2 else "Incomplete"
        length = distance(start, end)
        details = PassDetails(
            recipient=self.name_of(team, receiver) if outcome in ("Complete", "Pass Offside") else None,
            end_location=end, length=round(length, 1),
            angle=round(math.atan2(end[1] - start[1], end[0] - start[0]), 3),
            height=height or ("High Pass" if cross or length > 35 else "Ground Pass"),
            body_part=None if kind == "Throw-in" else self.rng.choice(["Right Foot"] * 3 + ["Left Foot"]),
            type=kind, technique=technique, cross=cross, outcome=outcome,
        )
        event = self.emit("Pass", team, passer, start, duration=max(0.4, length / 16), pass_=details)
        other = self.other(team)
        if outcome == "Complete":
            self.ball, self.holder, self.last_pass = end, receiver, event
            return True
        self.last_pass = None
        if outcome == "Pass Offside":
            self.emit("Offside", team, receiver, end, duration=0)
            self.set_restart("free_kick", other, flip(end), (15, 30))
        elif outcome == "Out":
            if end[0] >= 118:
                self.set_restart("goal_kick", other, (6.0, 40.0), (20, 32))
            else:
                self.set_restart("throw_in", other, flip((end[0], 0.5 if end[1] < 40 else 79.5)), (10, 22))
        elif cross:
            self.clearance(end)
        else:
            self.win_ball(other, flip(end), self.rng.choice(["Interception", "Ball Recovery"]))
        return False

    def carry(self, target: Point | None = None, safe: bool = False) -> bool:
        team, start = self.poss_team, self.ball
        if target is None:
            dx = self.rng.gauss(14 if self.counter_steps else 7, 4)
            target = (start[0] + dx, start[1] + self.rng.gauss(0, 5))
        end = clamp(*target)
        self.emit("Carry", team, self.holder, start, duration=max(0.5, distance(start, end) / 4.5),
                  carry=CarryDetails(end_location=end))
        self.ball = end
        if not safe and self.rng.random() < (0.1 if end[0] > 60 else 0.06):
            self.emit("Dispossessed", team, self.holder, end, duration=0.3, gap=0.2)
            self.tackle_won(end)
            return False
        return True

    def tackle_won(self, at: Point) -> None:
        other = self.other(self.poss_team)
        pos = self.near(other, flip(at))
        self.emit("Duel", other, pos, flip(at), duration=0.3, outcome="Won")
        self.take_over(other, flip(at), pos)

    def dribble(self) -> None:
        team, (x, y) = self.poss_team, self.ball
        beaten = self.rng.random() < 0.5 + 0.2 * (self.sides[team].strength - 0.5)
        self.emit("Dribble", team, self.holder, self.ball, duration=1.0,
                  outcome="Complete" if beaten else "Incomplete")
        if beaten:
            self.ball = clamp(x + self.rng.uniform(4, 8), y + self.rng.gauss(0, 4))
        else:
            self.tackle_won(self.ball)

    def cross(self) -> None:
        target = (self.rng.gauss(110, 3), self.rng.gauss(40, 7))
        receiver = self.near(self.poss_team, target, exclude=self.holder, lines=("FWD", "MID"))
        if self.pass_ball(target, cross=True, success=0.28, recipient=receiver, offside_ok=False):
            if self.rng.random() < 0.55:
                self.shoot(body_part="Head", first_time=True)

    def clearance(self, at: Point) -> None:
        """A cross or corner is cleared: the second ball can go either way, or out for a corner."""
        attackers = self.poss_team
        defenders = self.other(attackers)
        self.emit("Clearance", defenders, self.near(defenders, flip(at)), flip(at), duration=0.5)
        roll = self.rng.random()
        if roll < 0.3:
            self.set_restart("corner", attackers, (119.5, 0.5 if at[1] < 40 else 79.5), (20, 35))
        elif roll < 0.6:
            self.win_ball(defenders, (self.rng.uniform(25, 45), self.rng.uniform(10, 70)))
        else:
            self.take_over(attackers, (self.rng.uniform(80, 92), self.rng.uniform(15, 65)))
            self.holder = self.near(attackers, self.ball)
            self.emit("Ball Recovery", attackers, self.holder, self.ball, duration=0.3)

    # ---------- shots ----------

    def shoot(self, body_part: str | None = None, shot_type: str = "Open Play", first_time: bool = False,
              forced: str | None = None) -> str:
        """A shot from where the ball is. `forced` fixes the outcome (the script). Returns the outcome."""
        team, location, shooter = self.poss_team, self.ball, self.holder
        body_part = body_part or self.rng.choice(["Right Foot"] * 3 + ["Left Foot"] * 2)
        pressure = shot_type == "Open Play" and self.rng.random() < 0.4
        details = ShotDetails(outcome="Saved", body_part=body_part, type=shot_type,
                              technique="Normal", first_time=first_time)
        probe = MatchEvent(id="probe", index=0, period=1, minute=0, second=0, type="Shot", team=team,
                           location=location, under_pressure=pressure, shot=details)
        xg = shot_xg(probe) or 0.0
        strength = self.sides[team].strength
        if forced:
            outcome = forced
        elif not self.scenario.scripted and self.rng.random() < xg * (0.6 + 0.4 * (strength - 0.5)):
            outcome = "Goal"
        elif shot_type == "Penalty":
            outcome = self.rng.choices(["Saved", "Off T", "Post"], [7, 2, 1])[0]
        else:
            outcome = self.rng.choices(["Blocked", "Saved", "Off T", "Post", "Wayward"],
                                       [27, 34, 29, 4, 6])[0]
        details.outcome = outcome
        details.end_location = self._shot_end(outcome)
        event = self.emit("Shot", team, shooter, location, duration=0.8, under_pressure=pressure,
                          shot=details)
        if self.last_pass and self.last_pass.pass_ and self.last_pass.pass_.recipient == event.player:
            self.last_pass.pass_.shot_assist = True
            self.last_pass.pass_.goal_assist = outcome == "Goal"
        self.last_pass = None
        self._after_shot(outcome, location)
        return outcome

    def _shot_end(self, outcome: str) -> tuple[float, ...]:
        if outcome in ("Goal", "Saved"):
            return 120.0, round(self.rng.uniform(36.5, 43.5), 1), round(self.rng.uniform(0.2, 2.3), 2)
        if outcome == "Post":
            return 120.0, self.rng.choice([36.0, 44.0]), round(self.rng.uniform(0.5, 2.0), 2)
        if outcome == "Blocked":
            return clamp(self.ball[0] + 3, self.ball[1])
        return 120.0, round(self.rng.choice([self.rng.uniform(28, 35.5), self.rng.uniform(44.5, 52)]), 1)

    def _after_shot(self, outcome: str, location: Point) -> None:
        attackers = self.poss_team
        defenders = self.other(attackers)
        corner = (119.5, 0.5 if location[1] < 40 else 79.5)
        if outcome == "Goal":
            self.set_restart("kickoff", defenders, (60.0, 40.0), (50, 75))
        elif outcome == "Saved":
            self.emit("Goal Keeper", defenders, GK, (2.0, 40.0), duration=0.5, outcome="Success")
            if self.rng.random() < 0.45:
                self.set_restart("corner", attackers, corner, (20, 35))
            else:
                self.take_over(defenders, (6.0, 40.0), GK)
        elif outcome == "Blocked":
            self.emit("Block", defenders, self.near(defenders, flip(location)), flip(location), duration=0.3)
            roll = self.rng.random()
            if roll < 0.45:
                self.set_restart("corner", attackers, corner, (20, 35))
            elif roll < 0.75:
                self.win_ball(defenders, clamp(*flip((location[0] - 6, location[1]))))
            else:
                self.ball = clamp(location[0] - 8, location[1])
        elif outcome == "Post" and self.rng.random() < 0.5:
            self.ball = clamp(location[0] - 4, location[1])
            self.holder = self.near(attackers, self.ball)
        elif outcome == "Post":
            self.win_ball(defenders, (8.0, 40.0))
        else:
            self.set_restart("goal_kick", defenders, (6.0, 40.0), (20, 32))

    # ---------- fouls and cards ----------

    def foul(self, fouling_team: str, fouler: str | None = None, card: str | None = None,
             penalty: bool | None = None) -> None:
        """`fouling_team` fouls the player on the ball. The script can fix who, the card and a penalty."""
        victims = self.other(fouling_team)
        x, y = self.ball
        if penalty is None:
            penalty = in_box(x, y)
            if penalty and self.scenario.scripted:  # only the script gives penalties
                penalty, x = False, 100.0
                self.ball = (x, y)
        fouler = fouler or self.near(fouling_team, flip(self.ball))
        side = self.sides[fouling_team]
        name = self.name_of(fouling_team, fouler)
        if card is None:
            roll = self.rng.random()
            if roll < 0.003 and not self.scenario.scripted:
                card = "Red Card"
            elif roll < 0.17:
                card = "Yellow Card"
            if card == "Yellow Card" and name in side.booked:
                card = None if self.scenario.scripted or name in self.protected else "Second Yellow"
        self.emit("Foul Committed", fouling_team, fouler, flip(self.ball), duration=0.5, gap=0.1,
                  foul=FoulDetails(card=card, penalty=penalty))
        self.emit("Foul Won", victims, self.holder, self.ball, duration=0)
        if card == "Yellow Card":
            side.booked.add(name)
        if card in ("Red Card", "Second Yellow"):
            del side.on_pitch[fouler]
            side.strength -= 0.07
        dead = (40, 70) if penalty else (25, 50) if card else (15, 30)
        if penalty:
            self.set_restart("penalty", victims, (108.0, 40.0), dead)
        else:
            self.set_restart("free_kick", victims, self.ball, dead)

    # ---------- restarts ----------

    def do_restart(self) -> None:
        restart, self.restart = self.restart, None
        self.make_due_substitutions()
        team, location = restart.team, restart.location
        if team != self.poss_team or restart.kind == "kickoff":
            self.poss_id += 1
        self.poss_team, self.ball, self.pattern = team, location, PATTERNS[restart.kind]
        self.counter_steps, self.last_pass = 0, None
        x, y = location
        rng = self.rng
        if restart.kind == "kickoff":
            on_pitch = self.sides[team].on_pitch
            self.holder = "Center Forward" if "Center Forward" in on_pitch else self.near(team, location)
            self.pass_ball((rng.gauss(48, 4), rng.gauss(40, 10)), kind="Kick Off", success=0.98)
        elif restart.kind == "throw_in":
            self.holder = self.near(team, location, lines=("DEF", "MID", "FWD"))
            inward = rng.uniform(6, 14) * (1 if y < 40 else -1)
            self.pass_ball((x + rng.gauss(4, 6), y + inward), kind="Throw-in", height="Low Pass",
                           success=0.88, offside_ok=False)
        elif restart.kind == "goal_kick":
            self.holder = GK
            if rng.random() < 0.55:
                self.pass_ball((rng.gauss(65, 8), rng.gauss(40, 18)), kind="Goal Kick", height="High Pass",
                               success=0.5)
            else:
                self.pass_ball((rng.gauss(20, 3), rng.choice([14.0, 66.0])), kind="Goal Kick", success=0.97)
        elif restart.kind == "corner":
            self.take_corner()
        elif restart.kind == "penalty":
            self.holder = self.near(team, location, lines=("FWD", "MID"))
            self.shoot(shot_type="Penalty")
        else:
            self.take_free_kick()

    def take_corner(self, scorer: str | None = None) -> None:
        team, y = self.poss_team, self.ball[1]
        self.holder = "Right Wing" if y > 40 else "Left Wing"
        if self.holder not in self.sides[team].on_pitch:
            self.holder = self.near(team, self.ball, lines=("MID", "FWD"))
        target = (self.rng.gauss(111, 3), self.rng.gauss(40, 6))
        receiver = scorer or self.near(team, target, exclude=self.holder, lines=("DEF", "FWD", "MID"))
        complete = self.pass_ball(target, kind="Corner", cross=True, recipient=receiver,
                                  technique=self.rng.choice(["Inswinging", "Outswinging"]),
                                  success=1.0 if scorer else 0.33)
        if complete and (scorer or self.rng.random() < 0.55):
            self.shoot(body_part="Head", first_time=True, forced="Goal" if scorer else None)

    def take_free_kick(self) -> None:
        team, (x, y) = self.poss_team, self.ball
        self.holder = self.near(team, self.ball, lines=("MID", "FWD", "DEF"))
        if x >= 84 and 24 <= y <= 56 and self.rng.random() < 0.4:
            self.shoot(shot_type="Free Kick")
        elif x >= 80:
            target = (self.rng.gauss(109, 3), self.rng.gauss(40, 8))
            receiver = self.near(team, target, exclude=self.holder, lines=("DEF", "FWD"))
            if self.pass_ball(target, kind="Free Kick", cross=True, success=0.3, recipient=receiver,
                              offside_ok=False) and self.rng.random() < 0.5:
                self.shoot(body_part="Head", first_time=True)
        else:
            self.pass_ball(kind="Free Kick", success=0.9)

    def make_due_substitutions(self) -> None:
        if self.period != 2:
            return
        for side in self.sides.values():
            while side.sub_minutes and self.t >= side.sub_minutes[0] * 60 and side.bench:
                side.sub_minutes.pop(0)
                incoming = side.bench.pop(self.rng.randrange(len(side.bench)))
                can_go = [pos for pos, p in side.on_pitch.items()
                          if pos != GK and p.name not in self.protected and p.name not in side.came_on]
                options = [pos for pos in can_go if side.on_pitch[pos].line == incoming.line] or can_go
                if not options:
                    continue
                pos = self.rng.choice(options)
                self.emit("Substitution", side.name, pos, duration=0, gap=self.rng.uniform(15, 30),
                          substitution=SubstitutionDetails(replacement=incoming.name, outcome="Tactical"))
                side.on_pitch[pos] = incoming
                side.came_on.add(incoming.name)

    # ---------- scripted beats ----------

    def play_beat(self, beat: Beat) -> None:
        team, other = beat.team, self.other(beat.team)
        player = self.position_of(team, beat.player)
        if beat.kind == "red_card":
            if self.poss_team != other:
                self.win_ball(other, flip(self.ball))
            self.carry(safe=True)
            fouler = player or self.near(team, flip(self.ball), lines=("DEF", "MID"))
            self.foul(team, fouler=fouler, card="Red Card", penalty=False)
            return
        style = {"penalty_miss": "penalty", "goal": beat.style}.get(beat.kind, "open_play")
        outcome = "Goal" if beat.kind == "goal" else "Saved" if beat.kind == "penalty_miss" else \
            self.rng.choice(["Post", "Off T"])
        shooter = player or self.near(team, (105.0, 40.0), lines=("FWD",))
        rng = self.rng

        if style == "counter":
            if self.poss_team == team:  # they lose it first, then win it back and break
                self.holder = self.holder or self.near(team, self.ball)
                self.emit("Miscontrol", team, self.holder, self.ball, duration=0.5)
                self.win_ball(other, flip(self.ball))
            self.take_over(team, (rng.uniform(30, 40), rng.uniform(20, 60)), pattern="From Counter")
            self.holder = self.near(team, self.ball, lines=("DEF", "MID"))
            self.emit("Interception", team, self.holder, self.ball, duration=0.3, outcome="Won")
            self.carry((self.ball[0] + rng.uniform(15, 22), self.ball[1] + rng.gauss(0, 6)), safe=True)
            self.pass_ball((rng.gauss(97, 2), rng.gauss(40, 5)), technique="Through Ball", success=1.0,
                           recipient=shooter, offside_ok=False)
            self.carry((rng.uniform(105, 109), rng.uniform(34, 46)), safe=True)
            self.shoot(forced=outcome)
            return

        if self.poss_team != team:
            self.win_ball(team, flip(self.ball), "Interception")
        self.pattern = "Regular Play" if style != "penalty" else self.pattern
        if style == "open_play":
            self.pass_ball((rng.gauss(78, 4), rng.gauss(40, 15)), success=1.0, offside_ok=False)
            self.pass_ball((rng.gauss(98, 3), rng.gauss(40, 6)), technique=rng.choice(["Through Ball", None]),
                           success=1.0, recipient=shooter, offside_ok=False)
            if beat.kind == "big_miss":  # a sitter: close and central, so it really is a big chance
                self.carry((rng.uniform(110, 113), rng.uniform(37, 43)), safe=True)
            else:
                self.carry((rng.uniform(106, 110), rng.uniform(33, 47)), safe=True)
            self.shoot(forced=outcome, first_time=beat.kind == "big_miss")
        elif style == "long_range":
            self.pass_ball((rng.gauss(82, 3), rng.gauss(40, 6)), success=1.0, recipient=shooter,
                           offside_ok=False)
            self.carry((rng.uniform(89, 93), rng.uniform(35, 45)), safe=True)
            self.shoot(forced=outcome)
        elif style == "corner":
            self.pass_ball((rng.gauss(100, 3), rng.choice([12.0, 68.0])), success=1.0, offside_ok=False)
            self.carry((rng.uniform(104, 108), rng.uniform(26, 32)), safe=True)
            self.shoot(forced="Saved")  # the keeper tips it behind...
            if self.restart and self.restart.kind == "corner":
                self.restart = None
            else:
                self.t += rng.uniform(20, 35)
            corner = (119.5, rng.choice([0.5, 79.5]))
            self.poss_id += 1
            self.poss_team, self.ball, self.pattern = team, corner, "From Corner"
            self.take_corner(scorer=shooter)  # ...and from the corner, a header
        elif style == "penalty":
            self.carry((rng.uniform(104, 108), rng.uniform(30, 50)), safe=True)
            self.foul(other, card=rng.choice([None, "Yellow Card"]), penalty=True)  # also waits for the kick
            self.restart = None
            self.poss_id += 1
            self.poss_team, self.ball, self.pattern = team, (108.0, 40.0), "Other"
            self.holder = shooter
            self.shoot(shot_type="Penalty", forced=outcome)


def generate_match(scenario: Scenario, seed: int, match_id: str | None = None) -> Match:
    """A full synthetic match: the same scenario and seed always give the same match."""
    return MatchSimulator(scenario, seed, match_id).run()
