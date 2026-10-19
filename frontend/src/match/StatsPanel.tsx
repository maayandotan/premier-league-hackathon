import type { MatchInfo, MatchStats } from './types'

/** Scoreboard plus the live numbers the agents will explain. */
export function StatsPanel({ info, stats }: { info: MatchInfo; stats: MatchStats }) {
  const home = info.home.name
  const away = info.away.name
  const both = (values: Record<string, number>, digits = 0) =>
    `${(values[home] ?? 0).toFixed(digits)} – ${(values[away] ?? 0).toFixed(digits)}`
  // Momentum runs -1 (away on top) to +1 (home on top); show it as a bar from the middle.
  const momentum = stats.momentum.value
  const barWidth = `${Math.abs(momentum) * 50}%`

  return (
    <section className="stats">
      <div className="scoreboard">
        <span className="team">{home}</span>
        <span className="score">{both(stats.score)}</span>
        <span className="team">{away}</span>
        <span className="clock">{stats.minute}'</span>
      </div>
      {stats.shootout && <p className="shootout">Penalties: {both(stats.shootout)}</p>}

      <div className="momentum" title={`momentum ${momentum}`}>
        <div className={`fill ${momentum >= 0 ? 'home' : 'away'}`} style={{ width: barWidth }} />
      </div>
      <p className="momentum-label">
        {stats.momentum.leader ? `${stats.momentum.leader} on top` : 'Evenly matched'} · {stats.tempo.label}
      </p>

      <dl className="numbers">
        <dt>Possession</dt><dd>{both(stats.possession)}%</dd>
        <dt>Last 10 min</dt><dd>{both(stats.possession_last_10)}%</dd>
        <dt>Shots</dt><dd>{both(stats.shots)}</dd>
        <dt>xG</dt><dd>{both(stats.xg, 2)}</dd>
        <dt>Progressive passes</dt><dd>{both(stats.progressive_passes)}</dd>
      </dl>
    </section>
  )
}
