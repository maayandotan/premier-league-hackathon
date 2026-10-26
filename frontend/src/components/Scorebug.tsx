import type { FeedStatus } from '../match/useMatchFeed'
import { teamCode } from '../match/teams'
import type { MatchInfo, MatchStats } from '../match/types'
import { useT } from '../i18n'
import { CRESTS, SHAPES } from './crests'

/** A club's crest: its badge shape in its two colours, with the emblem from its name and its code
 * (crests.ts). Our own designs, no real club badge. A club without a design gets a plain shield. */
export function Crest({ name, side, code, color }: {
  name: string
  side: 'home' | 'away'
  code?: string // the club's own code and colour, when the match data has them
  color?: string
}) {
  const label = code ?? teamCode(name)
  const design = CRESTS[label]
  if (!design) {
    return (
      <svg className={`crest ${side}`} viewBox="0 0 40 46" aria-hidden="true">
        <path d={SHAPES.shield.outer} className="crest-shield" />
        <path d={SHAPES.shield.inner} className="crest-inner" style={color ? { fill: color } : undefined} />
        <text x="20" y="27" textAnchor="middle">{label}</text>
      </svg>
    )
  }
  const shape = SHAPES[design.shape]
  return (
    <svg className={`crest ${side} designed`} viewBox="0 0 40 46" aria-hidden="true">
      <path d={shape.outer} style={{ fill: design.secondary }} />
      <path d={shape.inner} className="crest-inner" style={color ? { fill: color } : undefined} />
      <g transform={`translate(12 ${design.shape === 'round' ? 10 : 10.5})`} style={{ color: design.secondary }}>
        {design.fill && <path d={design.fill} fill="currentColor" />}
        {design.stroke && <path d={design.stroke} fill="none" stroke="currentColor" strokeWidth={1.5}
          strokeLinecap="round" strokeLinejoin="round" />}
      </g>
      <text x="20" y={design.shape === 'round' ? 34.5 : 34} textAnchor="middle" className="crest-code"
        style={{ fill: design.secondary }}>{label}</text>
    </svg>
  )
}

const PERIODS: Record<number, string> = { 1: '1st half', 2: '2nd half', 3: 'Extra time', 4: 'Extra time', 5: 'Penalties' }

/** The TV-style score strip at the top of the broadcast. */
export function Scorebug({ info, stats, status, period }: {
  info: MatchInfo
  stats: MatchStats | null
  status: FeedStatus
  period: number | null
}) {
  const t = useT()
  const home = info.home.name
  const away = info.away.name
  const score = stats?.score ?? { [home]: 0, [away]: 0 }
  const phase = t(status === 'ended' ? 'Full time' : period ? PERIODS[period] : 'Pre-match')
  return (
    <div className="scorebug" role="group" aria-label={`${home} ${score[home] ?? 0}, ${away} ${score[away] ?? 0}`}>
      <div className="competition">
        <span>{info.competition ?? t('Match')}</span>
        <span className="phase">{phase}</span>
      </div>
      <div className="team home">
        <Crest name={home} side="home" code={info.home.code} color={info.home.color} />
        <span className="name">{home}</span>
      </div>
      <div className="score">
        <span>{score[home] ?? 0}</span>
        <span className="dash">–</span>
        <span>{score[away] ?? 0}</span>
      </div>
      <div className="team away">
        <span className="name">{away}</span>
        <Crest name={away} side="away" code={info.away.code} color={info.away.color} />
      </div>
      <div className="clock">
        {status === 'live' && <span className="live-dot" aria-hidden="true" />}
        <span>{status === 'ended' ? t('FT') : stats ? `${stats.minute}'` : '—'}</span>
      </div>
      {stats?.shootout && (
        <div className="shootout">{t('Penalties')} {stats.shootout[home]} – {stats.shootout[away]}</div>
      )}
    </div>
  )
}
