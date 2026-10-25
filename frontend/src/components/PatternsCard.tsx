import type { MatchInfo, MatchStats } from '../match/types'

/** The tactical detectors, live: what each team has been doing in the last 15 minutes, and where it
 * has entered the final third all match. For the analyst layout. */
export function PatternsCard({ info, stats }: { info: MatchInfo; stats: MatchStats }) {
  const teams = [info.home.name, info.away.name]
  return (
    <section className="card patterns" aria-label="Tactical patterns">
      <h2>Tactical patterns <span className="league-sub">last 15 minutes</span></h2>
      {teams.map((team) => {
        const p = stats.patterns?.[team]
        const entries = p?.final_third_entries_all_match ?? {}
        const total = Object.values(entries).reduce((a, b) => a + b, 0)
        return (
          <div key={team} className="pattern-team">
            <h3>{team}</h3>
            <ul>{(p?.last_15_minutes ?? ['no data yet']).map((line) => <li key={line}>{line}</li>)}</ul>
            {total > 0 && (
              <div className="channels" aria-label={`Final-third entries this match: ${total}`}>
                {(['left', 'centre', 'right'] as const).map((side) => (
                  <span key={side} style={{ flexGrow: entries[side] || 0.01 }} title={`${side}: ${entries[side]}`}>
                    {entries[side] ? `${side} ${entries[side]}` : ''}
                  </span>
                ))}
              </div>
            )}
          </div>
        )
      })}
      <p className="stat-note">Final-third entries this match by side, from each team's own attacking view.</p>
    </section>
  )
}
