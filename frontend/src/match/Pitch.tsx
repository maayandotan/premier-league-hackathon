import type { MatchEvent, RankedEvent } from './types'

/**
 * A live "match centre" pitch (#22): the ball moving from event to event, the player on the
 * ball, a trail of the last few moves, shots towards goal and a flash on goals.
 *
 * Only what the data knows: each event has the acting player's location (and where a pass or
 * carry ended). There's no tracking data, so we don't invent the other 21 players.
 *
 * Coordinates are 120 x 80 and each event is from its own team's view (attacking to x = 120).
 * We draw the home team attacking right and flip the away team so both sides line up.
 */

const TRAIL = 6
// Events that tell us where the ball is.
const BALL_EVENTS = new Set([
  'Pass', 'Carry', 'Shot', 'Dribble', 'Ball Recovery', 'Interception', 'Clearance', 'Goal Keeper',
  'Miscontrol', 'Dispossessed', 'Foul Won', 'Block',
])

type Point = [number, number]

interface Move {
  id: string
  home: boolean
  kind: 'pass' | 'carry' | 'shot' | 'touch'
  from: Point
  to: Point | null
  complete: boolean
  goal: boolean
  player?: string
  recipient?: string
}

const surname = (name?: string) => name?.split(' ').slice(-1)[0]

function toMove(e: MatchEvent, homeTeam: string): Move | null {
  if (!e.location || !BALL_EVENTS.has(e.type)) return null
  const home = e.team === homeTeam
  const view = ([x, y]: number[]): Point => (home ? [x, y] : [120 - x, 80 - y])
  const from = view(e.location)
  if (e.shot) {
    const target = e.shot.end_location ? view(e.shot.end_location.slice(0, 2)) : view([120, 40])
    return { id: e.id, home, kind: 'shot', from, to: target, complete: e.shot.outcome === 'Goal',
             goal: e.shot.outcome === 'Goal', player: e.player }
  }
  if (e.pass?.end_location) {
    return { id: e.id, home, kind: 'pass', from, to: view(e.pass.end_location),
             complete: e.pass.outcome === 'Complete', goal: false, player: e.player, recipient: e.pass.recipient }
  }
  if (e.carry?.end_location) {
    return { id: e.id, home, kind: 'carry', from, to: view(e.carry.end_location), complete: true, goal: false,
             player: e.player }
  }
  return { id: e.id, home, kind: 'touch', from, to: null, complete: true, goal: false, player: e.player }
}

function PitchMarkings() {
  return (
    <g className="markings">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <rect key={i} x={i * 20} y={0} width={20} height={80} className={i % 2 ? 'stripe-dark' : 'stripe-light'} />
      ))}
      <rect x={0} y={0} width={120} height={80} className="line" />
      <line x1={60} y1={0} x2={60} y2={80} className="line" />
      <circle cx={60} cy={40} r={10} className="line" />
      <circle cx={60} cy={40} r={0.5} className="spot" />
      {[0, 1].map((side) => {
        const mirror = (x: number) => (side ? 120 - x : x)
        const box = (depth: number, top: number) => (
          <rect x={side ? 120 - depth : 0} y={top} width={depth} height={80 - 2 * top} className="line" />
        )
        return (
          <g key={side}>
            {box(18, 18)}
            {box(6, 30)}
            <circle cx={mirror(12)} cy={40} r={0.5} className="spot" />
            <rect x={side ? 120 : -2} y={36} width={2} height={8} className="goal" />
          </g>
        )
      })}
    </g>
  )
}

export function Pitch({ events, homeTeam, awayTeam }: { events: RankedEvent[]; homeTeam: string; awayTeam: string }) {
  // events arrive newest first; collect the latest moves, oldest first for drawing
  const moves: Move[] = []
  for (const { event } of events) {
    const move = toMove(event, homeTeam)
    if (move) moves.unshift(move)
    if (moves.length === TRAIL) break
  }
  const latest = moves[moves.length - 1]
  // A goal is followed by the keeper's event in the same second: keep the flash while the goal is
  // in the trail, and keep the ball in the net while it's one of the last two moves.
  const goal = [...moves].reverse().find((m) => m.goal)
  const ballInNet = goal && moves.indexOf(goal) >= moves.length - 2
  const ball = ballInNet ? goal.to! : latest ? latest.to ?? latest.from : ([60, 40] as Point)

  return (
    <div className="pitch-wrap">
      <div className="pitch-legend">
        <span className="team home">{homeTeam} →</span>
        <span className="team away">← {awayTeam}</span>
      </div>
      <svg viewBox="-4 -4 128 88" className="pitch" role="img" aria-label="Live pitch: where the ball is">
        <PitchMarkings />

        {moves.map((m, i) => {
          if (!m.to) return null
          const age = (moves.length - 1 - i) / TRAIL
          return (
            <line key={m.id} x1={m.from[0]} y1={m.from[1]} x2={m.to[0]} y2={m.to[1]}
              className={`trail ${m.home ? 'home' : 'away'} ${m.kind} ${m.complete ? '' : 'failed'}`}
              style={{ opacity: 1 - age * 0.8 }} />
          )
        })}

        {goal && (
          <rect key={goal.id} x={goal.home ? 118 : 0} y={30} width={2} height={20} className="goal-flash" />
        )}

        {latest && (
          <g className={`player ${latest.home ? 'home' : 'away'}`}>
            <circle cx={latest.from[0]} cy={latest.from[1]} r={2.2} />
            <text x={latest.from[0]} y={latest.from[1] - 3.5}>{surname(latest.player)}</text>
            {latest.recipient && latest.to && (
              <text x={latest.to[0]} y={latest.to[1] + 6} className="recipient">{surname(latest.recipient)}</text>
            )}
          </g>
        )}

        <g className="ball" style={{ transform: `translate(${ball[0]}px, ${ball[1]}px)` }}>
          <circle r={1.3} />
        </g>
      </svg>
    </div>
  )
}
