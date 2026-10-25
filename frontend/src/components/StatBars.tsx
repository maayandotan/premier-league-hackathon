import type { MatchInfo, MatchStats } from '../match/types'
import { useT } from '../i18n'

function Row({ label, home, away, format = (v) => String(v), hint }: {
  label: string
  hint?: string // a plain-words line under the bar, for beginners
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
      {hint && <p className="stat-hint">{hint}</p>}
    </div>
  )
}

/** Head-to-head numbers, like a half-time graphic. A beginner sees two, in plain words, each explained;
 * a fan the usual set; an analyst the lot. */
export function StatBars({ info, stats, level = 'fan' }: { info: MatchInfo; stats: MatchStats; level?: string }) {
  const t = useT()
  const h = info.home.name
  const a = info.away.name
  if (level === 'beginner') {
    return (
      <section className="card stats beginner" aria-label={t('Match stats')}>
        <h2>{t('The match in numbers')}</h2>
        <Row label={t('Who has had the ball')} home={stats.possession[h]} away={stats.possession[a]}
          format={(v) => `${Math.round(v)}%`} hint={t('The team with more of the ball usually controls the game.')} />
        <Row label={t('Shots at goal')} home={stats.shots[h]} away={stats.shots[a]}
          hint={t('Every attempt to score, whether it went in, was saved or missed.')} />
      </section>
    )
  }
  return (
    <section className="card stats" aria-label={t('Match stats')}>
      <h2>{t('Match stats')}</h2>
      <Row label={t('Possession')} home={stats.possession[h]} away={stats.possession[a]} format={(v) => `${Math.round(v)}%`} />
      <Row label={t('Last 10 min')} home={stats.possession_last_10[h]} away={stats.possession_last_10[a]}
        format={(v) => `${Math.round(v)}%`} />
      <Row label={t('Shots')} home={stats.shots[h]} away={stats.shots[a]} />
      <Row label={t('Expected goals')} home={stats.xg[h]} away={stats.xg[a]} format={(v) => v.toFixed(2)} />
      <Row label={t('Progressive passes')} home={stats.progressive_passes[h]} away={stats.progressive_passes[a]} />
      {level === 'analyst' && (
        <p className="stat-note">
          {t('Tempo: {label} ({n} possession changes a minute) · Momentum {m} (home +1, away −1)', {
            label: t(stats.tempo.label), n: stats.tempo.possession_changes_per_min.toFixed(1),
            m: `${stats.momentum.value > 0 ? '+' : ''}${stats.momentum.value.toFixed(2)}`,
          })}
        </p>
      )}
    </section>
  )
}

/** Who's on top right now: a bar that leans towards the dominant team (home left, away right). */
export function MomentumBar({ stats }: { stats: MatchStats }) {
  const t = useT()
  const value = stats.momentum.value // -1 away ... +1 home
  const leader = stats.momentum.leader
  return (
    <div className="momentum" aria-label={`${t('Momentum')}: ${leader ?? t('Evenly matched')}`}>
      <div className="momentum-head">
        <span>{t('Momentum')}</span>
        <span className="momentum-label">{leader ? t('{team} on top', { team: leader }) : t('Evenly matched')}</span>
      </div>
      <div className="momentum-track">
        <span className="midline" />
        <span className={`momentum-fill ${value >= 0 ? 'home' : 'away'}`} style={{ width: `${Math.abs(value) * 50}%` }} />
      </div>
    </div>
  )
}
