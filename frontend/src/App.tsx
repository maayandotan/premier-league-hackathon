import { useEffect, useState } from 'react'
import { AnalystQATable } from './components/AnalystQATable'
import { CommentaryFeed } from './components/CommentaryFeed'
import { EventTicker } from './components/EventTicker'
import { BallIcon, PlayIcon, RestartIcon, SpeakerIcon } from './components/Icons'
import { type Level, LevelPicker } from './components/LevelPicker'
import { MatchTimeline } from './components/MatchTimeline'
import { GoalBanner, LowerThird } from './components/PitchOverlays'
import { QuestionBox } from './components/QuestionBox'
import { Scorebug } from './components/Scorebug'
import { MomentumBar, StatBars } from './components/StatBars'
import { BeginnerGuide } from './components/BeginnerGuide'
import { ClubPanel } from './components/ClubPanel'
import { PatternsCard } from './components/PatternsCard'
import { XgTimeline } from './components/XgTimeline'
import { Crest } from './components/Scorebug'
import { LeagueTable } from './components/LeagueTable'
import { PreMatch } from './components/PreMatch'
import { Pitch } from './match/Pitch'
import type { ClubSeason, League, MatchInfo } from './match/types'
import { useMatchFeed } from './match/useMatchFeed'

// Pick the match from the URL, e.g. ?source=synthetic:red_card&speed=20&start=60 (default: the comeback)
const params = new URLSearchParams(location.search)
const feedOptions = {
  source: params.get('source') ?? 'synthetic:comeback',
  speed: Number(params.get('speed') ?? 4),
  start: Number(params.get('start') ?? 0),
  level: params.get('level') ?? 'fan',
}

/** The teams and line-ups before kick-off, for the pre-match screen (null until loaded, or if it fails:
 * then the plain kick-off card shows). */
function usePreMatchInfo(source: string): MatchInfo | null {
  const [info, setInfo] = useState<MatchInfo | null>(null)
  useEffect(() => {
    let current = true
    fetch(`/api/match-info?source=${encodeURIComponent(source)}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => { if (current) setInfo(data) })
      .catch(() => {})
    return () => { current = false }
  }, [source])
  return info
}

/** The Meridian League: today's fixtures, the table and the top scorers (null if unavailable). */
function useLeague(refresh: boolean): League | null {
  const [league, setLeague] = useState<League | null>(null)
  useEffect(() => {
    let current = true
    fetch('/api/league')
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => { if (current) setLeague(data) })
      .catch(() => {})
    return () => { current = false }
  }, [refresh])
  return league
}

const TEAM_KEY = 'match-intelligence.team'

/** The viewer's club: from ?team= or remembered from last time (browser storage can fail: then not). */
function useFavourite(): [string | null, (team: string | null) => void] {
  const [team, setTeam] = useState<string | null>(() => {
    try { return params.get('team') ?? localStorage.getItem(TEAM_KEY) } catch { return null }
  })
  const choose = (next: string | null) => {
    setTeam(next)
    try { if (next) localStorage.setItem(TEAM_KEY, next); else localStorage.removeItem(TEAM_KEY) } catch { /* fine */ }
  }
  return [team, choose]
}

/** The viewer's club's season (refetched at full time, when the result is in). */
function useClubSeason(team: string | null, refresh: boolean): ClubSeason | null {
  const [season, setSeason] = useState<ClubSeason | null>(null)
  useEffect(() => {
    let current = true
    if (team) {
      fetch(`/api/league/club?name=${encodeURIComponent(team)}`)
        .then((response) => (response.ok ? response.json() : null))
        .then((data) => { if (current) setSeason(data) })
        .catch(() => {})
    }
    return () => { current = false }
  }, [team, refresh])
  return team ? season : null
}

/** Text that reads on a club colour: dark on light colours (Elmsworth yellow), white on dark ones. */
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function inkFor(hex: string): string {
  return luminance(hex) > 0.55 ? '#0b1220' : '#ffffff'
}

export default function App() {
  const [team, setTeam] = useFavourite()
  const { status, error, info, events, lines, questions, stats, muted, speakingId, level, setLevel, ask,
    setListening, toggleMute, start, connected, xgHistory } = useMatchFeed({ ...feedOptions, team })
  const preInfo = usePreMatchInfo(feedOptions.source)
  const league = useLeague(status === 'ended') // fetched again at full time: the result is in the table
  const club = league?.clubs.find((c) => c.name === team) ?? null
  const clubSeason = useClubSeason(club ? team : null, status === 'ended')
  // The club colour goes on the whole page (html), not just the app box, so the background takes it too.
  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('themed', !!club)
    if (club) {
      root.style.setProperty('--accent', club.color)
      root.style.setProperty('--accent-ink', inkFor(club.color))
      // A near-white club (Whitecliff) tints the page with its second colour: white on dark is just grey.
      root.style.setProperty('--tint', luminance(club.color) > 0.8 ? club.secondary : club.color)
    } else {
      for (const name of ['--accent', '--accent-ink', '--tint']) root.style.removeProperty(name)
    }
  }, [club])
  const answered = new Set(lines.map((l) => l.reply_to))
  const waiting = questions.some((q) => !answered.has(q.id))
  const live = status === 'live'
  const canAsk = connected && (live || status === 'ended') // questions stay open after full time
  const period = events[0]?.event.period ?? null
  const scoreText = info && stats ? `${stats.score[info.home.name]}–${stats.score[info.away.name]}` : ''

  return (
    <div className={`app level-${level}${info ? '' : ' pre-match'}${club ? ' themed' : ''}`}>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><BallIcon size={24} /></span>
          <div>
            <h1>Match Intelligence</h1>
            <p>AI commentary at your level</p>
          </div>
        </div>
        <div className="controls">
          {club && (
            <span className="club-badge" title={`Supporting ${club.name}`}>
              <Crest name={club.name} side="home" code={club.code} color={club.color} />
              <span>{club.name}</span>
            </span>
          )}
          <LevelPicker value={level as Level} onChange={setLevel} />
          <button className="icon-button" onClick={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'}
            title={muted ? 'Sound off' : 'Sound on'}>
            <SpeakerIcon muted={muted} />
          </button>
          <button className="kickoff" onClick={start}>
            {live ? <RestartIcon size={16} /> : <PlayIcon size={16} />} {live ? 'Restart' : 'Kick off'}
          </button>
        </div>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      <main className="broadcast">
        <div className="stage">
          {info ? (
            <>
              <Scorebug info={info} stats={stats} status={status} period={period} />
              {stats && <MatchTimeline events={events} homeTeam={info.home.name} minute={stats.minute} />}
              <section className="card pitch-card">
                <div className="pitch-stage">
                  <Pitch events={events} homeTeam={info.home.name} awayTeam={info.away.name} />
                  <GoalBanner events={events} score={scoreText} />
                  <LowerThird lines={lines} speakingId={speakingId} />
                </div>
                {stats && <MomentumBar stats={stats} />}
              </section>
              <AnalystQATable
                questions={questions}
                lines={lines}
                speakingId={speakingId}
                onAsk={ask}
                canAsk={canAsk}
              />
            </>
          ) : preInfo ? (
            <PreMatch info={preInfo} level={level as Level} onLevel={setLevel} onKickOff={start}
              fixtures={league?.fixtures} matchday={league?.matchday} source={feedOptions.source}
              clubs={league?.clubs} team={team} onTeam={setTeam} />
          ) : (
            <>
              <section className="card hero">
                <div className="hero-text">
                  <span className="eyebrow">Live · AI broadcast</span>
                  <h2>Two AI commentators.<br />Your level.</h2>
                  <p>A caller for the action, an analyst for the why, and a crowd that roars on every goal.
                    Ask them anything, by voice, while the match goes on.</p>
                  <button className="kickoff big" onClick={start}><PlayIcon size={20} /> Kick off</button>
                  <p className="hint"><SpeakerIcon size={16} /> Turn your sound on</p>
                </div>
              </section>
              <AnalystQATable
                questions={questions}
                lines={lines}
                speakingId={speakingId}
                onAsk={ask}
                canAsk={canAsk}
              />
            </>
          )}
        </div>

        <aside className="side">
          <CommentaryFeed lines={lines} questions={questions} speakingId={speakingId} />
          <QuestionBox open={canAsk} fullTime={status === 'ended'} waiting={waiting} onAsk={ask}
            onListening={setListening} />
        </aside>

        <div className="lower">
          {club && clubSeason && <ClubPanel club={club} season={clubSeason}
            today={league?.fixtures.find((f) => f.home === club.name || f.away === club.name)} />}
          {info && stats && <StatBars info={info} stats={stats} level={level} />}
          {info && stats && level === 'analyst' && <XgTimeline info={info} history={xgHistory} />}
          {info && stats && level === 'analyst' && <PatternsCard info={info} stats={stats} />}
          {level === 'beginner' && <BeginnerGuide />}
          {info && stats && <EventTicker events={events} homeTeam={info.home.name} />}
          {league && <LeagueTable league={league} mine={team} simple={level === 'beginner'}
            teams={[(info ?? preInfo)?.home.name, (info ?? preInfo)?.away.name].filter((t): t is string => !!t)} />}
        </div>
      </main>

      <footer className="footer">
        <span>Fictional teams and players · Crowd audio: “Free Crowd Cheering Sounds” by Gregor Quendel, CC BY 4.0</span>
      </footer>
    </div>
  )
}
