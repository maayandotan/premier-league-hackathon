import type { MatchInfo, MatchStats } from '../match/types'

function Row({ label, home, away, format = (v) => String(v) }: {
  label: string
  home: number
  away: number
  format?: (v: number) => string
}) {
  const total = home + away
  const share = total ? (home / total) * 100 : 50
  return (
    <div className="stat-row">
      <span className="value home">{format(home)}</span>
      <span className="label">{label}</span>
      <span className="value away">{format(away)}</span>
      <div className="bar" aria-hidden="true">
        <span className="fill home" style={{ width: `${share}%` }} />
        <span className="fill away" style={{ width: `${100 - share}%` }} />
      </div>
    </div>
  )
}

/** Head-to-head numbers, like a half-time graphic. */
export function StatBars({ info, stats }: { info: MatchInfo; stats: MatchStats }) {
  const h = info.home.name
  const a = info.away.name
  return (
    <section className="card stats" aria-label="Match stats">
      <h2>Match stats</h2>
      <Row label="Possession" home={stats.possession[h]} away={stats.possession[a]} format={(v) => `${Math.round(v)}%`} />
      <Row label="Last 10 min" home={stats.possession_last_10[h]} away={stats.possession_last_10[a]}
        format={(v) => `${Math.round(v)}%`} />
      <Row label="Shots" home={stats.shots[h]} away={stats.shots[a]} />
      <Row label="Expected goals" home={stats.xg[h]} away={stats.xg[a]} format={(v) => v.toFixed(2)} />
      <Row label="Progressive passes" home={stats.progressive_passes[h]} away={stats.progressive_passes[a]} />
    </section>
  )
}

/** Who's on top right now: a bar that leans towards the dominant team (home left, away right). */
export function MomentumBar({ stats }: { stats: MatchStats }) {
  const value = stats.momentum.value // -1 away ... +1 home
  const leader = stats.momentum.leader
  return (
    <div className="momentum" aria-label={`Momentum: ${leader ?? 'even'}`}>
      <div className="momentum-head">
        <span>Momentum</span>
        <span className="momentum-label">{leader ? `${leader} on top` : 'Evenly matched'}</span>
      </div>
      <div className="momentum-track">
        <span className="midline" />
        <span className={`momentum-fill ${value >= 0 ? 'home' : 'away'}`} style={{ width: `${Math.abs(value) * 50}%` }} />
      </div>
    </div>
  )
}
