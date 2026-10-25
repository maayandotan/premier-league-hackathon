import { useEffect, useState } from 'react'
import { CommentaryFeed } from './components/CommentaryFeed'
import { EventTicker } from './components/EventTicker'
import { BallIcon, PlayIcon, RestartIcon, SpeakerIcon } from './components/Icons'
import { type Level, LevelPicker } from './components/LevelPicker'
import { MatchTimeline } from './components/MatchTimeline'
import { GoalBanner, LowerThird } from './components/PitchOverlays'
import { QuestionBox } from './components/QuestionBox'
import { Scorebug } from './components/Scorebug'
import { MomentumBar, StatBars } from './components/StatBars'
import { LeagueTable } from './components/LeagueTable'
import { PreMatch } from './components/PreMatch'
import { Pitch } from './match/Pitch'
import type { League, MatchInfo } from './match/types'
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

export default function App() {
  const { status, error, info, events, lines, questions, stats, muted, speakingId, level, setLevel, ask,
    setListening, toggleMute, start, connected } = useMatchFeed(feedOptions)
  const preInfo = usePreMatchInfo(feedOptions.source)
  const league = useLeague(status === 'ended') // fetched again at full time: the result is in the table
  const answered = new Set(lines.map((l) => l.reply_to))
  const waiting = questions.some((q) => !answered.has(q.id))
  const live = status === 'live'
  const canAsk = connected && (live || status === 'ended') // questions stay open after full time
  const period = events[0]?.event.period ?? null
  const scoreText = info && stats ? `${stats.score[info.home.name]}–${stats.score[info.away.name]}` : ''

  return (
    <div className={info ? 'app' : 'app pre-match'}>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><BallIcon size={24} /></span>
          <div>
            <h1>Match Intelligence</h1>
            <p>AI commentary at your level</p>
          </div>
        </div>
        <div className="controls">
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
            </>
          ) : preInfo ? (
            <PreMatch info={preInfo} level={level as Level} onLevel={setLevel} onKickOff={start}
              fixtures={league?.fixtures} matchday={league?.matchday} source={feedOptions.source} />
          ) : (
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
          )}
        </div>

        <aside className="side">
          <CommentaryFeed lines={lines} questions={questions} speakingId={speakingId} />
          <QuestionBox open={canAsk} fullTime={status === 'ended'} waiting={waiting} onAsk={ask}
            onListening={setListening} />
        </aside>

        <div className="lower">
          {info && stats && <StatBars info={info} stats={stats} />}
          {info && stats && <EventTicker events={events} homeTeam={info.home.name} />}
          {league && <LeagueTable league={league}
            teams={[(info ?? preInfo)?.home.name, (info ?? preInfo)?.away.name].filter((t): t is string => !!t)} />}
        </div>
      </main>

      <footer className="footer">
        <span>Fictional teams and players · Crowd audio: “Free Crowd Cheering Sounds” by Gregor Quendel, CC BY 4.0</span>
      </footer>
    </div>
  )
}
