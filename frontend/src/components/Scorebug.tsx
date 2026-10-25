import type { FeedStatus } from '../match/useMatchFeed'
import { teamCode } from '../match/teams'
import type { MatchInfo, MatchStats } from '../match/types'

/** A plain shield with the team code: our own design, no real club badge. */
export function Crest({ name, side }: { name: string; side: 'home' | 'away' }) {
  return (
    <svg className={`crest ${side}`} viewBox="0 0 40 46" aria-hidden="true">
      <path d="M20 2 L37 8 V22 C37 33 29 40 20 44 C11 40 3 33 3 22 V8 Z" className="crest-shield" />
      <path d="M20 6 L33 10.5 V22 C33 31 27 36.5 20 40 C13 36.5 7 31 7 22 V10.5 Z" className="crest-inner" />
      <text x="20" y="27" textAnchor="middle">{teamCode(name)}</text>
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
  const home = info.home.name
  const away = info.away.name
  const score = stats?.score ?? { [home]: 0, [away]: 0 }
  const phase = status === 'ended' ? 'Full time' : period ? PERIODS[period] : 'Pre-match'
  return (
    <div className="scorebug" role="group" aria-label={`${home} ${score[home] ?? 0}, ${away} ${score[away] ?? 0}`}>
      <div className="competition">
        <span>{info.competition ?? 'Match'}</span>
        <span className="phase">{phase}</span>
      </div>
      <div className="team home">
        <Crest name={home} side="home" />
        <span className="name">{home}</span>
      </div>
      <div className="score">
        <span>{score[home] ?? 0}</span>
        <span className="dash">–</span>
        <span>{score[away] ?? 0}</span>
      </div>
      <div className="team away">
        <span className="name">{away}</span>
        <Crest name={away} side="away" />
      </div>
      <div className="clock">
        {status === 'live' && <span className="live-dot" aria-hidden="true" />}
        <span>{status === 'ended' ? 'FT' : stats ? `${stats.minute}'` : '—'}</span>
      </div>
      {stats?.shootout && (
        <div className="shootout">Penalties {stats.shootout[home]} – {stats.shootout[away]}</div>
      )}
    </div>
  )
}
