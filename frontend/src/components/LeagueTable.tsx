import type { League } from '../match/types'

/** The Meridian League table, with the two clubs in this match highlighted. Before today's match it's
 * the table after the matchdays already played; at full time it updates with this result. */
export function LeagueTable({ league, teams, mine, simple }: {
  league: League
  teams: string[]
  mine?: string | null
  simple?: boolean // beginner: position, club, points
}) {
  return (
    <section className={`card league${simple ? ' simple' : ''}`} aria-label="League table">
      <h2>{league.league} <span className="league-sub">Matchday {league.matchday}</span></h2>
      <table>
        <thead>
          <tr><th>#</th><th className="team">Club</th><th>P</th><th>GD</th><th>Pts</th><th className="form">Form</th></tr>
        </thead>
        <tbody>
          {league.table.map((row) => (
            <tr key={row.team}
              className={[teams.includes(row.team) && 'playing', row.team === mine && 'mine'].filter(Boolean).join(' ') || undefined}>
              <td>{row.position}</td>
              <td className="team">{row.team}</td>
              <td>{row.played}</td>
              <td>{row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}</td>
              <td className="pts">{row.points}</td>
              <td className="form">
                {row.form.split('').map((r, i) => <span key={i} className={`form-${r}`}>{r}</span>)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
