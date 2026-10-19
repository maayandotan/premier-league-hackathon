import type { FeedStatus } from '../match/useMatchFeed'
import type { MatchInfo, MatchStats } from '../match/types'

/** A TV-style 3-letter code: "Westvale United" -> "WEU", "Argentina" -> "ARG". */
const teamCode = (name: string) => {
  const words = name.split(/\s+/).filter((w) => !/^(fc|cf|afc|sc)$/i.test(w))
  const code = words.length === 1 ? words[0].slice(0, 3) : words[0].slice(0, 2) + words[1][0]
  return code.toUpperCase()
}

function Crest({ name, side }: { name: string; side: 'home' | 'away' }) {
  return <span className={`crest ${side}`} aria-hidden="true">{teamCode(name)}</span>
}

/** The TV-style score strip at the top of the broadcast. */
export function Scorebug({ info, stats, status }: { info: MatchInfo; stats: MatchStats | null; status: FeedStatus }) {
  const home = info.home.name
  const away = info.away.name
  const score = stats?.score ?? { [home]: 0, [away]: 0 }
  return (
    <div className="scorebug" role="group" aria-label="Score">
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
