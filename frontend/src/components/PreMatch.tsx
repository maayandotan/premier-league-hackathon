import type { LeagueFixture, MatchInfo, Player } from '../match/types'
import { PlayIcon, SpeakerIcon } from './Icons'
import type { Level } from './LevelPicker'
import { Crest } from './Scorebug'

const POSITIONS = ['Goalkeeper', 'Right Back', 'Right Center Back', 'Left Center Back', 'Left Back',
  'Center Defensive Midfield', 'Right Center Midfield', 'Left Center Midfield', 'Right Wing', 'Left Wing',
  'Center Forward']
const SHORT: Record<string, string> = {
  Goalkeeper: 'GK', 'Right Back': 'RB', 'Right Center Back': 'CB', 'Left Center Back': 'CB', 'Left Back': 'LB',
  'Center Defensive Midfield': 'DM', 'Right Center Midfield': 'CM', 'Left Center Midfield': 'CM',
  'Right Wing': 'RW', 'Left Wing': 'LW', 'Center Forward': 'CF',
}
const CHOICES: { id: Level; label: string; title: string; hint: string }[] = [
  { id: 'beginner', label: 'Beginner', title: 'New to football', hint: 'Everything explained, no jargon' },
  { id: 'fan', label: 'Fan', title: 'I follow the game', hint: 'Clear football talk, a few numbers' },
  { id: 'analyst', label: 'Analyst', title: 'Give me the numbers', hint: 'xG, possession and the tactics' },
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
export function PreMatch({ info, level, onLevel, onKickOff, fixtures, matchday, source }: {
  info: MatchInfo
  level: Level
  onLevel: (level: Level) => void
  onKickOff: () => void
  fixtures?: LeagueFixture[] // today's matchday: pick another match to watch
  matchday?: number
  source: string
}) {
  return (
    <section className="card prematch" aria-label="Before kick-off">
      {fixtures && fixtures.length > 0 && (
        <nav className="pm-fixtures" aria-label={`Matchday ${matchday} fixtures`}>
          <span className="pm-fixtures-title">Matchday {matchday}: pick a match</span>
          <div className="pm-fixture-list">
            {fixtures.map((f) => (
              <a key={f.source} href={withSource(f.source)} className={f.source === source ? 'active' : undefined}
                aria-current={f.source === source ? 'true' : undefined}>
                <span>{f.home}</span>
                <span className="pm-fixture-score">{f.result ?? 'v'}</span>
                <span>{f.away}</span>
              </a>
            ))}
          </div>
        </nav>
      )}
      <span className="eyebrow">{info.competition ?? 'Match'}{matchday ? ` · Matchday ${matchday}` : ''} · Kick-off</span>
      <div className="pm-teams">
        <div className="pm-team home">
          <Crest name={info.home.name} side="home" code={info.home.code} color={info.home.color} />
          <span>{info.home.name}</span>
        </div>
        <span className="pm-vs">vs</span>
        <div className="pm-team away">
          <span>{info.away.name}</span>
          <Crest name={info.away.name} side="away" code={info.away.code} color={info.away.color} />
        </div>
      </div>
      <div className="pm-lineups" aria-label="Starting line-ups">
        <Lineup players={info.home.players ?? []} side="home" />
        <Lineup players={info.away.players ?? []} side="away" />
      </div>
      <p className="pm-voices">
        Your commentators: <strong>Guy</strong> calls the action, <strong>Sonia</strong> explains why it matters.
        Ask them anything while the match goes on.
      </p>
      <fieldset className="pm-level">
        <legend>How well do you know football?</legend>
        <div className="pm-choices">
          {CHOICES.map((c) => (
            <label key={c.id} className={level === c.id ? 'active' : ''}>
              <input type="radio" name="level" value={c.id} checked={level === c.id} onChange={() => onLevel(c.id)} />
              <span className="pm-choice-level">{c.label}</span>
              <span className="pm-choice-title">{c.title}</span>
              <span className="pm-choice-hint">{c.hint}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="pm-go">
        <button className="kickoff big" onClick={onKickOff}><PlayIcon size={20} /> Kick off</button>
        <span className="hint"><SpeakerIcon size={16} /> Turn your sound on</span>
      </div>
    </section>
  )
}
