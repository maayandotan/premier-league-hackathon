import { useT } from '../i18n'
import { Pitch } from '../match/Pitch'
import type { AnswerFocus, MatchInfo, MatchStats, RankedEvent } from '../match/types'
import { MicIcon } from './Icons'
import { Crest } from './Scorebug'

/** The match stays on screen while the viewer reads the stats below: a small live pitch with the
 * score, like a video's mini player. The match is the centre of the experience; everything else is
 * around it. */
export function MiniPitch({ info, stats, events, level, focus, focusId, onAsk }: {
  info: MatchInfo
  stats: MatchStats | null
  events: RankedEvent[]
  level: string
  focus?: AnswerFocus | null
  focusId?: string
  onAsk: () => void // back to the Ask Roy dock
}) {
  const t = useT()
  const home = info.home.name
  const away = info.away.name
  return (
    <aside className="mini-pitch" aria-label={t('The match, while you scroll')}>
      <div className="mini-head">
        <Crest name={home} side="home" code={info.home.code} color={info.home.color} />
        <strong className="mini-score">{stats?.score[home] ?? 0}–{stats?.score[away] ?? 0}</strong>
        <Crest name={away} side="away" code={info.away.code} color={info.away.color} />
        <span className="mini-clock">{stats ? `${stats.minute}'` : ''}</span>
        <button type="button" className="mini-ask" onClick={onAsk}>
          <MicIcon size={16} /> {t('Ask {name}', { name: t.voice('Roy') })}
        </button>
      </div>
      <Pitch events={events} homeTeam={home} awayTeam={away} info={info} stats={stats} level={level}
        focus={focus} focusId={focusId} />
    </aside>
  )
}
