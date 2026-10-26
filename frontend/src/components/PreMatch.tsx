import type { Club, LeagueFixture, MatchInfo, Player } from '../match/types'
import { MicIcon, PlayIcon, SpeakerIcon } from './Icons'
import type { Level } from './LevelPicker'
import { Crest } from './Scorebug'
import { useT } from '../i18n'

const POSITIONS = ['Goalkeeper', 'Right Back', 'Right Center Back', 'Left Center Back', 'Left Back',
  'Center Defensive Midfield', 'Right Center Midfield', 'Left Center Midfield', 'Right Wing', 'Left Wing',
  'Center Forward']
const SHORT: Record<string, string> = {
  Goalkeeper: 'GK', 'Right Back': 'RB', 'Right Center Back': 'CB', 'Left Center Back': 'CB', 'Left Back': 'LB',
  'Center Defensive Midfield': 'DM', 'Right Center Midfield': 'CM', 'Left Center Midfield': 'CM',
  'Right Wing': 'RW', 'Left Wing': 'LW', 'Center Forward': 'CF',
}
const CHOICES: { id: Level; label: string; title: string; hint: string }[] = [
  { id: 'beginner', label: 'BEGINNER', title: 'New to football', hint: 'Everything explained, no jargon' },
  { id: 'fan', label: 'FAN', title: 'I follow the game', hint: 'Clear football talk, a few numbers' },
  { id: 'analyst', label: 'ANALYST', title: 'Give me the numbers', hint: 'xG, possession and the tactics' },
]

/** The page's URL with another match: the other options (level, speed) stay, the start minute goes. */
function withSource(source: string): string {
  const params = new URLSearchParams(location.search)
  params.set('source', source)
  params.delete('start')
  return `?${params}`
}

function Lineup({ players, side }: { players: Player[]; side: 'home' | 'away' }) {
  const starters = players.filter((p) => p.starter !== false)
    .sort((a, b) => POSITIONS.indexOf(a.position ?? '') - POSITIONS.indexOf(b.position ?? ''))
  return (
    <ol className={`pm-lineup ${side}`}>
      {starters.map((p) => (
        <li key={p.name}>
          <span className="pm-number">{p.jersey_number}</span>
          <span className="pm-name">{p.name}</span>
          <span className="pm-pos">{SHORT[p.position ?? ''] ?? ''}</span>
        </li>
      ))}
    </ol>
  )
}

/** Before kick-off, like a broadcast's opening: the teams, the line-ups, who's commentating, and the
 * viewer's level, chosen before the first line is spoken. */
export function PreMatch({ info, level, onLevel, onKickOff, fixtures, matchday, source, clubs, team, onTeam }: {
  info: MatchInfo
  level: Level
  onLevel: (level: Level) => void
  onKickOff: () => void
  fixtures?: LeagueFixture[] // today's matchday: pick another match to watch
  matchday?: number
  source: string
  clubs?: Club[] // pick a favourite: the page takes its colours, the commentary relates to it
  team: string | null
  onTeam: (team: string | null) => void
}) {
  const t = useT()
  return (
    <section className="card prematch" aria-label={t('Before kick-off')}>
      {fixtures && fixtures.length > 0 && (
        <nav className="pm-fixtures" aria-label={t('Matchday {n}', { n: matchday ?? '' })}>
          <span className="pm-fixtures-title">{t('Matchday {n}: pick a match', { n: matchday ?? '' })}</span>
          <div className="pm-fixture-list">
            {fixtures.map((f) => (
              <a key={f.source} href={withSource(f.source)} className={f.source === source ? 'active' : undefined}
                aria-current={f.source === source ? 'true' : undefined}>
                <span>{f.home}</span>
                <span className="pm-fixture-score">{f.result ?? t('v')}</span>
                <span>{f.away}</span>
              </a>
            ))}
          </div>
        </nav>
      )}
      <span className="eyebrow">{info.competition ?? t('Match')}{matchday ? ` · ${t('Matchday {n}', { n: matchday })}` : ''} · {t('Kick-off')}</span>
      <div className="pm-teams">
        <div className="pm-team home">
          <Crest name={info.home.name} side="home" code={info.home.code} color={info.home.color} />
          <span>{info.home.name}</span>
        </div>
        <span className="pm-vs">{t('vs')}</span>
        <div className="pm-team away">
          <span>{info.away.name}</span>
          <Crest name={info.away.name} side="away" code={info.away.code} color={info.away.color} />
        </div>
      </div>
      <div className="pm-lineups" aria-label={t('Starting line-ups')}>
        <Lineup players={info.home.players ?? []} side="home" />
        <Lineup players={info.away.players ?? []} side="away" />
      </div>
      <p className="pm-voices">
        {t('Your commentators:')} <strong>{t.voice('Davis')}</strong> {t('calls the action,')} <strong>{t.voice('Roy')}</strong>{' '}
        {t('explains why it matters.')}
      </p>
      <div className="pm-ask">
        <span className="pm-ask-mic" aria-hidden="true"><MicIcon size={22} /></span>
        <div>
          <strong>{t('Ask {name} anything, any time', { name: t.voice('Roy') })}</strong>
          <span>{t('“Why was that a foul?” “Who has been better?” Ask by voice or text: the match keeps playing while he answers, at your level.')}</span>
        </div>
      </div>
      {clubs && clubs.length > 0 && (
        <fieldset className="pm-club">
          <legend>{t('Your club')} <span>{t('(optional)')}</span></legend>
          <div className="pm-club-list">
            {clubs.map((c) => (
              <button key={c.name} type="button" className={team === c.name ? 'active' : undefined}
                aria-pressed={team === c.name} title={c.name} aria-label={c.name}
                onClick={() => onTeam(team === c.name ? null : c.name)}>
                <Crest name={c.name} side="home" code={c.code} color={c.color} />
              </button>
            ))}
          </div>
          <span className="pm-club-name">{team ?? t('Neutral: no club picked')}</span>
        </fieldset>
      )}
      <fieldset className="pm-level">
        <legend>{t('How well do you know football?')}</legend>
        <div className="pm-choices">
          {CHOICES.map((c) => (
            <label key={c.id} className={level === c.id ? 'active' : ''} data-level={c.id}>
              <input type="radio" name="level" value={c.id} checked={level === c.id} onChange={() => onLevel(c.id)} />
              <span className="pm-choice-level">{t(c.label)}</span>
              <span className="pm-choice-title">{t(c.title)}</span>
              <span className="pm-choice-hint">{t(c.hint)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="pm-go">
        <button className="kickoff big" onClick={onKickOff}><PlayIcon size={20} /> {t('Kick off')}</button>
        <span className="hint"><SpeakerIcon size={16} /> {t('Turn your sound on')}</span>
      </div>
    </section>
  )
}
