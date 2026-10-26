import type { MatchEvent, MatchInfo, RankedEvent } from './types'

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

const BOARDS = 'YOUR CALL · MERIDIAN LEAGUE · '

/** The stadium as a TV camera sees it: the apron and the LED boards, mown grass under floodlights,
 * every marking a real pitch has (arcs, corners, nets). */
function PitchMarkings() {
  return (
    <g className="markings">
      <defs>
        <radialGradient id="floodlight" cx="50%" cy="45%" r="65%">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.12" />
          <stop offset="60%" stopColor="#fff" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.35" />
        </radialGradient>
        <pattern id="net" width="0.8" height="0.8" patternUnits="userSpaceOnUse">
          <path d="M0 0 L0.8 0.8 M0.8 0 L0 0.8" stroke="rgba(255,255,255,0.55)" strokeWidth="0.12" />
        </pattern>
        <filter id="ball-glow" x="-2" y="-2" width="5" height="5">
          <feGaussianBlur stdDeviation="0.8" />
        </filter>
      </defs>
      <rect x={-7} y={-12} width={134} height={98} rx={2} className="apron" />
      <rect x={2} y={-10.5} width={116} height={3.4} rx={0.6} className="boards" />
      <text x={60} y={-8} className="boards-text" textAnchor="middle">{BOARDS.repeat(4)}</text>
      {Array.from({ length: 12 }, (_, i) => (
        <rect key={i} x={i * 10} y={0} width={10} height={80} className={i % 2 ? 'stripe-dark' : 'stripe-light'} />
      ))}
      <rect x={0} y={0} width={120} height={80} fill="url(#floodlight)" />
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
            {/* the penalty arc ("the D"): 10 yards from the spot, outside the box */}
            <path d={side ? 'M102 32 A10 10 0 0 0 102 48' : 'M18 32 A10 10 0 0 1 18 48'} className="line" />
            <rect x={side ? 120 : -2.4} y={36} width={2.4} height={8} fill="url(#net)" className="goal" />
          </g>
        )
      })}
      {/* corner arcs */}
      <path d="M0 1 A1 1 0 0 0 1 0 M119 0 A1 1 0 0 0 120 1 M120 79 A1 1 0 0 0 119 80 M1 80 A1 1 0 0 0 0 79"
        className="line" />
    </g>
  )
}

// A shirt, about 6.5 x 6 pitch units, centred on the player's spot.
const SHIRT = 'M-2 -2.6 L-0.8 -3 Q0 -2.2 0.8 -3 L2 -2.6 L3.2 -1.2 L2.3 -0.3 L1.8 -0.8 L1.8 2.8 L-1.8 2.8 ' +
  'L-1.8 -0.8 L-2.3 -0.3 L-3.2 -1.2 Z'

/** Text that reads on a shirt colour: dark on light shirts, white on dark ones. */
function inkOn(hex: string): string {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 ? '#0b1220' : '#ffffff'
}

export function Pitch({ events, homeTeam, awayTeam, info }: {
  events: RankedEvent[]
  homeTeam: string
  awayTeam: string
  info?: MatchInfo // shirt numbers and club colours
}) {
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
  // The player on the ball wears his club's shirt, with his number (the line-ups have both).
  const side = latest?.home ? info?.home : info?.away
  const shirt = {
    color: side?.color ?? (latest?.home ? '#3b82f6' : '#f43f5e'),
    number: side?.players?.find((p) => p.name === latest?.player)?.jersey_number,
  }

  return (
    <div className="pitch-wrap">
      <div className="pitch-legend">
        <span className="team home">{homeTeam} →</span>
        <span className="team away">← {awayTeam}</span>
      </div>
      <svg viewBox="-7 -12 134 98" className="pitch" role="img" aria-label="Live pitch: where the ball is">
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
            <g transform={`translate(${latest.from[0]} ${latest.from[1]})`} className="shirt">
              <path d={SHIRT} style={{ fill: shirt.color }} />
              {shirt.number !== undefined && (
                <text y={1.6} className="shirt-number" style={{ fill: inkOn(shirt.color) }}>{shirt.number}</text>
              )}
            </g>
            <text x={latest.from[0]} y={latest.from[1] - 4.2}>{surname(latest.player)}</text>
            {latest.recipient && latest.to && (
              <text x={latest.to[0]} y={latest.to[1] + 6} className="recipient">{surname(latest.recipient)}</text>
            )}
          </g>
        )}

        <g className="ball" style={{ transform: `translate(${ball[0]}px, ${ball[1]}px)` }}>
          <ellipse cx={0.5} cy={1.1} rx={1.4} ry={0.6} className="ball-shadow" />
          <circle r={2.2} className="ball-halo" filter="url(#ball-glow)" />
          <circle r={1.3} />
        </g>
      </svg>
    </div>
  )
}
