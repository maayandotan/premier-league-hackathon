import { useState } from 'react'
import { CommentaryFeed } from './components/CommentaryFeed'
import { EventTicker } from './components/EventTicker'
import { type Level, LevelPicker } from './components/LevelPicker'
import { Scorebug } from './components/Scorebug'
import { MomentumBar, StatBars } from './components/StatBars'
import { Pitch } from './match/Pitch'
import { useMatchFeed } from './match/useMatchFeed'

// Pick the match from the URL, e.g. ?source=synthetic:sample_match&speed=20&start=60
const params = new URLSearchParams(location.search)
const feedOptions = {
  source: params.get('source') ?? 'demo',
  speed: Number(params.get('speed') ?? 4),
  start: Number(params.get('start') ?? 0),
}

export default function App() {
  const [level, setLevel] = useState<Level>('fan')
  const { status, error, info, events, lines, stats, muted, speakingId, toggleMute, start } = useMatchFeed(feedOptions)
  const live = status === 'live'

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">⚽</span>
          <div>
            <h1>Match Intelligence</h1>
            <p>AI commentary at your level</p>
          </div>
        </div>
        <div className="controls">
          <LevelPicker value={level} onChange={setLevel} />
          <button className="icon-button" onClick={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'}
            title={muted ? 'Sound off' : 'Sound on'}>
            {muted ? '🔇' : '🔊'}
          </button>
          <button className="kickoff" onClick={start}>{live ? '↻ Restart' : '▶ Kick off'}</button>
        </div>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      <main className="broadcast">
        <div className="stage">
          {info ? (
            <>
              <Scorebug info={info} stats={stats} status={status} />
              <section className="card pitch-card">
                <Pitch events={events} homeTeam={info.home.name} awayTeam={info.away.name} />
                {stats && <MomentumBar stats={stats} />}
              </section>
            </>
          ) : (
            <section className="card hero">
              <div className="hero-text">
                <span className="eyebrow">Live · AI broadcast</span>
                <h2>Two AI commentators.<br />Your level.</h2>
                <p>A caller for the action, an analyst for the why, and a crowd that roars on every goal.</p>
                <button className="kickoff big" onClick={start}>▶ Kick off</button>
                <p className="hint">🔊 Turn your sound on</p>
              </div>
            </section>
          )}
        </div>

        <aside className="side">
          <CommentaryFeed lines={lines} speakingId={speakingId} />
        </aside>

        {info && stats && (
          <div className="lower">
            <StatBars info={info} stats={stats} />
            <EventTicker events={events} homeTeam={info.home.name} />
          </div>
        )}
      </main>

      <footer className="footer">
        <span>{feedOptions.source} · ×{feedOptions.speed}</span>
        <span>Crowd audio: “Free Crowd Cheering Sounds” by Gregor Quendel, CC BY 4.0</span>
      </footer>
    </div>
  )
}
