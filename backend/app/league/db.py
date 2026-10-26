"""The league's results database (SQLite, inside the app).

On start it's filled from the pre-played season (season.json); every league match watched to full
time is added. Everything a fan asks is computed from it: the table, form, a club's top scorer and
top assister. The pre-played season is rebuilt on every start, so the table always works; matches
watched live are kept until the app restarts (decided Oct 25: no extra Azure resource).
"""
import sqlite3
import threading
from collections import Counter
from functools import lru_cache

from app.config import settings
from app.league.clubs import CLUBS, LEAGUE_NAME
from app.league.season import CURRENT_ROUND, fixtures, load_season
from app.synthetic.squads import captain

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY, round INTEGER, home TEXT, away TEXT,
                                    home_goals INTEGER, away_goals INTEGER, origin TEXT);
CREATE TABLE IF NOT EXISTS goals (match_id TEXT, minute INTEGER, team TEXT, scorer TEXT, assister TEXT,
                                  penalty INTEGER);
CREATE TABLE IF NOT EXISTS cards (match_id TEXT, minute INTEGER, team TEXT, player TEXT, card TEXT);
"""


class League:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.executescript(SCHEMA)
        if not self._db.execute("SELECT COUNT(*) FROM results").fetchone()[0]:
            for result in load_season()["results"]:
                self.record(result, origin="season")

    def record(self, result: dict, origin: str = "watched") -> bool:
        """Add a finished match; False if it was already there (watching it twice counts once)."""
        with self._lock, self._db:
            added = self._db.execute(
                "INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result["id"], result["round"], result["home"], result["away"], result["home_goals"],
                 result["away_goals"], origin)).rowcount
            if added:
                self._db.executemany("INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?)", [
                    (result["id"], g["minute"], g["team"], g["scorer"], g["assister"],
                     g.get("penalty", False))
                    for g in result["goals"]])
                self._db.executemany("INSERT INTO cards VALUES (?, ?, ?, ?, ?)", [
                    (result["id"], c["minute"], c["team"], c["player"], c["card"]) for c in result["cards"]])
        return bool(added)

    # ---------- what fans ask ----------

    def table(self) -> list[dict]:
        rows = {c.name: {"team": c.name, "played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0,
                         "goals_against": 0, "form": []} for c in CLUBS}
        with self._lock:
            results = self._db.execute(
                "SELECT home, away, home_goals, away_goals FROM results ORDER BY round, id").fetchall()
        for home, away, hg, ag in results:
            for team, scored, conceded in ((home, hg, ag), (away, ag, hg)):
                row = rows[team]
                row["played"] += 1
                row["goals_for"] += scored
                row["goals_against"] += conceded
                outcome = "W" if scored > conceded else "D" if scored == conceded else "L"
                row[{"W": "won", "D": "drawn", "L": "lost"}[outcome]] += 1
                row["form"].append(outcome)
        for row in rows.values():
            row["goal_difference"] = row["goals_for"] - row["goals_against"]
            row["points"] = 3 * row["won"] + row["drawn"]
            row["form"] = "".join(row["form"][-5:])  # oldest to newest
        ordered = sorted(rows.values(), key=lambda r: (-r["points"], -r["goal_difference"], -r["goals_for"],
                                                       r["team"]))
        for position, row in enumerate(ordered, 1):
            row["position"] = position
        return ordered

    def club(self, team: str) -> dict:
        """A club's season so far: where it stands, its captain, its top scorer and assister."""
        row = next(r for r in self.table() if r["team"] == team)
        with self._lock:
            goals = self._db.execute("SELECT scorer, assister FROM goals WHERE team = ?", (team,)).fetchall()
        scorers = Counter(s for s, _ in goals if s).most_common(3)
        assisters = Counter(a for _, a in goals if a).most_common(3)
        return {**row, "captain": captain(team),
                "top_scorers": [{"player": p, "goals": n} for p, n in scorers],
                "top_assisters": [{"player": p, "assists": n} for p, n in assisters]}

    def player_goals(self, player: str) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM goals WHERE scorer = ?", (player,)).fetchone()[0]

    def player_season(self, player: str) -> dict:
        """A player's league goals and assists so far."""
        with self._lock:
            goals = self._db.execute("SELECT COUNT(*) FROM goals WHERE scorer = ?", (player,)).fetchone()[0]
            assists = self._db.execute("SELECT COUNT(*) FROM goals WHERE assister = ?",
                                       (player,)).fetchone()[0]
        return {"league_goals": goals, "league_assists": assists}

    def player_profile(self, name: str, limit: int = 5) -> dict | None:
        """Detailed profile and last games data for a player (for Analyst investigation)."""
        from app.synthetic.squads import SQUADS, SquadPlayer

        found = None
        for team_name, squad in SQUADS.items():
            for p in squad:
                if p.name.lower() == name.lower() or name.lower() in p.name.lower():
                    found = (team_name, p)
                    break
            if found:
                break

        if not found:
            with self._lock:
                row = self._db.execute(
                    "SELECT team FROM goals WHERE scorer = ? OR assister = ? LIMIT 1", (name, name)
                ).fetchone()
            if row:
                found = (row[0], SquadPlayer(name=name, number=0, position="Forward"))
            else:
                return None

        team, player = found
        is_cap = captain(team) == player.name

        with self._lock:
            matches = self._db.execute(
                "SELECT id, round, home, away, home_goals, away_goals FROM results "
                "WHERE home = ? OR away = ? ORDER BY round DESC LIMIT ?",
                (team, team, limit)
            ).fetchall()
            goals_count = self._db.execute("SELECT COUNT(*) FROM goals WHERE scorer = ?", (player.name,)).fetchone()[0]
            assists_count = self._db.execute("SELECT COUNT(*) FROM goals WHERE assister = ?", (player.name,)).fetchone()[0]
            cards_count = self._db.execute("SELECT COUNT(*) FROM cards WHERE player = ?", (player.name,)).fetchone()[0]

        last_games = []
        for m_id, rnd, home, away, hg, ag in matches:
            is_home = (home == team)
            opponent = away if is_home else home
            team_goals = hg if is_home else ag
            opp_goals = ag if is_home else hg
            result = "W" if team_goals > opp_goals else ("D" if team_goals == opp_goals else "L")

            with self._lock:
                p_goals = self._db.execute(
                    "SELECT COUNT(*) FROM goals WHERE match_id = ? AND scorer = ?", (m_id, player.name)
                ).fetchone()[0]
                p_assists = self._db.execute(
                    "SELECT COUNT(*) FROM goals WHERE match_id = ? AND assister = ?", (m_id, player.name)
                ).fetchone()[0]
                p_cards = [
                    r[0] for r in self._db.execute(
                        "SELECT card FROM cards WHERE match_id = ? AND player = ?", (m_id, player.name)
                    ).fetchall()
                ]

            rating = 6.8 + (1.2 if result == "W" else (0.2 if result == "D" else -0.4))
            rating += p_goals * 1.1 + p_assists * 0.7 - len(p_cards) * 0.5
            rating = round(min(max(rating, 5.5), 9.9), 1)

            last_games.append({
                "match_id": m_id,
                "round": rnd,
                "opponent": opponent,
                "is_home": is_home,
                "score": f"{team_goals}-{opp_goals}",
                "result": result,
                "goals": p_goals,
                "assists": p_assists,
                "cards": p_cards,
                "rating": rating,
                "minutes": 90,
            })

        avg_rating = round(sum(g["rating"] for g in last_games) / max(len(last_games), 1), 1)

        return {
            "name": player.name,
            "number": player.number,
            "position": player.position,
            "team": team,
            "is_captain": is_cap,
            "season": {
                "goals": goals_count,
                "assists": assists_count,
                "cards": cards_count,
                "played": len(matches),
                "avg_rating": avg_rating,
            },
            "last_games": last_games,
        }

    def top_scorers(self, n: int = 5) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT scorer, team, COUNT(*) AS goals FROM goals GROUP BY scorer, team "
                                    "ORDER BY goals DESC, scorer LIMIT ?", (n,)).fetchall()
        return [{"player": p, "team": t, "goals": g} for p, t, g in rows]

    def todays_fixtures(self) -> list[dict]:
        from app.league.season import fixture_source  # avoid a cycle at import time

        with self._lock:
            played = {row[0]: row[1:] for row in self._db.execute(
                "SELECT home || '|' || away, home_goals, away_goals FROM results WHERE round = ?",
                (CURRENT_ROUND,))}
        out = []
        for home, away in fixtures()[CURRENT_ROUND - 1]:
            score = played.get(f"{home}|{away}")
            out.append({"home": home, "away": away, "source": fixture_source(home, away),
                        "result": f"{score[0]}-{score[1]}" if score else None})
        return out

    def summary(self) -> dict:
        return {"league": LEAGUE_NAME, "matchday": CURRENT_ROUND}


@lru_cache(maxsize=1)
def league() -> League:
    return League(settings.league_db)
