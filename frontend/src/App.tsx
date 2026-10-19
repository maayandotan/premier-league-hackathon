import { useState } from 'react'
import { useMatchFeed } from './match/useMatchFeed'

const LEVELS = ['Beginner', 'Fan', 'Analyst']

export default function App() {
  const [level, setLevel] = useState(1)
  const { status, events, lines, start } = useMatchFeed(4)

  return (
    <main>
      <header>
        <h1>Match Intelligence</h1>
        <p className="status" data-status={status}>{status}</p>
      </header>

      <section className="controls">
        <button onClick={start}>{status === 'live' ? 'Restart' : 'Start match'}</button>
        <label>
          Level: <strong>{LEVELS[level]}</strong>
          {/* Not wired to the backend yet: personalization comes with the agents. */}
          <input type="range" min={0} max={2} value={level} onChange={(e) => setLevel(Number(e.target.value))} />
        </label>
      </section>

      <div className="panels">
        <section>
          <h2>Commentary</h2>
          <ul>
            {lines.map((line, i) => (
              <li key={i} className={`line ${line.speaker}`} data-excitement={line.excitement}>
                <span className="speaker">{line.speaker}</span> {line.text}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2>Events</h2>
          <ul>
            {events.map((e) => (
              <li key={e.id}>
                <span className="clock">{e.minute}'{String(e.second).padStart(2, '0')}</span> {e.type} · {e.player ?? e.team}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}
