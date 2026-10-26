import { useEffect, useState } from 'react'
import { Logo } from '../components/Logo'
import { useT } from '../i18n'
import type { AnswerFocus, MatchEvent, MatchInfo, MatchStats, RankedEvent } from './types'

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
  high: boolean // a lofted pass or a cross: the ball goes through the air
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
             goal: e.shot.outcome === 'Goal', high: false, player: e.player }
  }
  if (e.pass?.end_location) {
    return { id: e.id, home, kind: 'pass', from, to: view(e.pass.end_location),
             complete: e.pass.outcome === 'Complete', goal: false, player: e.player, recipient: e.pass.recipient,
             high: e.pass.height === 'High Pass' || !!e.pass.cross }
  }
  if (e.carry?.end_location) {
    return { id: e.id, home, kind: 'carry', from, to: view(e.carry.end_location), complete: true, goal: false,
             high: false, player: e.player }
  }
  return { id: e.id, home, kind: 'touch', from, to: null, complete: true, goal: false, high: false, player: e.player }
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
        <pattern id="grass" width="2" height="2" patternUnits="userSpaceOnUse" patternTransform="rotate(25)">
          <path d="M0 0.5 H0.7 M1 1.5 H1.6" stroke="rgba(255,255,255,0.05)" strokeWidth="0.25" />
        </pattern>
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
      <rect x={0} y={0} width={120} height={80} fill="url(#grass)" />
      <rect x={0} y={0} width={120} height={80} fill="url(#floodlight)" />
      <g className="centre-logo" transform="translate(54.5 34.5)"><Logo size={11} /></g>
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

const FOCUS_MS = 20000 // how long the pitch points at what Roy's answer is about
const SHOT_MINUTES = 3 // the latest shot's circle stays this long (match minutes)
const LANES: Record<string, [number, number]> = { left: [0, 80 / 3], centre: [80 / 3, 160 / 3], right: [160 / 3, 80] }
const LANE_PATTERN = /^(\d+) of (\d+) final-third entries down the (left|centre|right)/

/** The lane a team keeps attacking down (from the pattern detector), lit in its attacking third. */
function Lanes({ stats, homeTeam, awayTeam, colors }: {
  stats?: MatchStats | null; homeTeam: string; awayTeam: string; colors: Record<string, string>
}) {
  return (
    <g className="lanes">
      {[homeTeam, awayTeam].map((team) => {
        const line = stats?.patterns?.[team]?.last_15_minutes.find((l) => LANE_PATTERN.test(l))
        const m = line?.match(LANE_PATTERN)
        if (!m) return null
        const home = team === homeTeam
        const [y0, y1] = LANES[m[3]]
        const top = home ? y0 : 80 - y1 // the away team attacks left, so its left is our bottom
        return (
          <g key={team}>
            <rect x={home ? 80 : 0} y={top} width={40} height={y1 - y0} className="lane"
              style={{ fill: `url(#lane-${home ? 'home' : 'away'})`, color: colors[team] }} />
            <clipPath id={`lane-clip-${home ? 'home' : 'away'}`}>
              <rect x={home ? 80 : 0} y={top} width={40} height={y1 - y0} />
            </clipPath>
            {/* arrows flowing towards goal: the direction of the attacks */}
            <g clipPath={`url(#lane-clip-${home ? 'home' : 'away'})`}>
              <g className={`lane-flow ${home ? 'right' : 'left'}`}>
                {[-10, 0, 10, 20, 30, 40].map((dx) => {
                  const x = (home ? 80 : 0) + dx
                  const mid = top + (y1 - y0) / 2
                  const d = home ? `M${x} ${mid - 3} L${x + 3} ${mid} L${x} ${mid + 3}`
                    : `M${x + 3} ${mid - 3} L${x} ${mid} L${x + 3} ${mid + 3}`
                  return <path key={dx} d={d} className="lane-arrow" style={{ color: colors[team] }} />
                })}
              </g>
            </g>
            <text x={home ? 100 : 20} y={top + 3.6} className="lane-label">{m[1]}/{m[2]}</text>
          </g>
        )
      })}
    </g>
  )
}

const VIEW = { x: -7, y: -12, w: 134, h: 98 } // the svg's viewBox: the pitch and its apron
const ZOOM = { play: 1.1, focus: 1.5, goal: 1.65 }
// During play the camera follows the ball only partway (and less up and down): a calm picture that
// drifts towards the action, not one that chases every pass.
const FOLLOW = { x: 0.4, y: 0.25 }
const CENTRE: Point = [60, 40]
const FLIGHT: Record<Move['kind'], number> = { shot: 0.32, pass: 0.62, carry: 0.95, touch: 0.4 } // seconds

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/** The TV camera: zoomed in a little and centred on `target`, never showing past the stadium's edge. */
function camera([x, y]: Point, zoom: number): string {
  const halfW = VIEW.w / (2 * zoom)
  const halfH = VIEW.h / (2 * zoom)
  const cx = clamp(x, VIEW.x + halfW, VIEW.x + VIEW.w - halfW)
  const cy = clamp(y, VIEW.y + halfH, VIEW.y + VIEW.h - halfH)
  return `translate(${VIEW.x + VIEW.w / 2 - zoom * cx}px, ${VIEW.y + VIEW.h / 2 - zoom * cy}px) scale(${zoom})`
}

/** A move's path: a lofted pass or a cross curves through the air, everything else is straight. */
function path(m: Move): string {
  const [x1, y1] = m.from
  const [x2, y2] = m.to!
  if (!m.high) return `M${x1} ${y1} L${x2} ${y2}`
  const length = Math.hypot(x2 - x1, y2 - y1)
  return `M${x1} ${y1} Q${(x1 + x2) / 2} ${(y1 + y2) / 2 - length * 0.28} ${x2} ${y2}`
}

function Shirt({ at, color, number, className, delay }: {
  at: Point; color: string; number?: number; className?: string; delay?: number
}) {
  return (
    <g className={`shirt-pos ${className ?? ''}`} style={{ transform: `translate(${at[0]}px, ${at[1]}px)`,
      animationDelay: delay ? `${delay}s` : undefined }}>
      <path d={SHIRT} style={{ fill: color }} className="shirt-body" />
      {number !== undefined && <text y={1.6} className="shirt-number" style={{ fill: inkOn(color) }}>{number}</text>}
    </g>
  )
}

export function Pitch({ events, homeTeam, awayTeam, info, stats, level = 'fan', focus, focusId }: {
  events: RankedEvent[]
  homeTeam: string
  awayTeam: string
  info?: MatchInfo // shirt numbers and club colours
  stats?: MatchStats | null // the live patterns, for the lit lanes
  level?: string
  focus?: AnswerFocus | null // what Roy's latest answer is about
  focusId?: string // that answer's id: a new answer shows its focus again
}) {
  const t = useT()
  const [focusDone, setFocusDone] = useState<string | null>(null)
  useEffect(() => {
    if (!focusId) return
    const timer = setTimeout(() => setFocusDone(focusId), FOCUS_MS)
    return () => clearTimeout(timer)
  }, [focusId])
  const colors: Record<string, string> = {
    [homeTeam]: info?.home.color ?? '#3b82f6', [awayTeam]: info?.away.color ?? '#f43f5e',
  }
  const drawn = (team: string, [x, y]: number[]): Point => (team === homeTeam ? [x, y] : [120 - x, 80 - y])
  const numberOf = (home: boolean, player?: string) =>
    (home ? info?.home : info?.away)?.players?.find((p) => p.name === player)?.jersey_number
  // events arrive newest first; collect the latest moves, oldest first for drawing
  const moves: Move[] = []
  for (const { event } of events) {
    const move = toMove(event, homeTeam)
    if (move) moves.unshift(move)
    if (moves.length === TRAIL) break
  }
  const latest = moves[moves.length - 1]
  // The latest shot, for a few match minutes: a circle sized by its chance of going in.
  const now = events[0]?.event.minute ?? 0
  const shot = events.find(({ event }) => event.shot && event.location && event.period < 5)
  const showShot = shot && now - shot.event.minute <= SHOT_MINUTES ? shot : undefined
  // A goal is followed by the keeper's event in the same second: keep the flash while the goal is
  // in the trail, and keep the ball in the net while it's one of the last two moves.
  const goal = [...moves].reverse().find((m) => m.goal)
  const ballInNet = goal && moves.indexOf(goal) >= moves.length - 2
  const ball = ballInNet ? goal.to! : latest ? latest.to ?? latest.from : ([60, 40] as Point)
  const flight = latest ? FLIGHT[latest.kind] : 0.6
  const focusOn = focus && focusId && focusDone !== focusId ? drawn(focus.team, focus.location) : null
  // The camera follows the ball, pushes in on a goal, and goes to what Roy is talking about.
  const drift: Point = [CENTRE[0] + (ball[0] - CENTRE[0]) * FOLLOW.x, CENTRE[1] + (ball[1] - CENTRE[1]) * FOLLOW.y]
  const view = focusOn ? camera(focusOn, ZOOM.focus) : ballInNet ? camera(goal.to!, ZOOM.goal) : camera(drift, ZOOM.play)
  const moment = !!focusOn || !!ballInNet // the camera moves quickly to a moment, slowly during play
  const runner = latest?.kind === 'carry' // a dribble: the shirt runs with the ball
  const color = (home: boolean) => colors[home ? homeTeam : awayTeam]

  return (
    <div className="pitch-wrap">
      <div className="pitch-legend">
        <span className="team home">{homeTeam} →</span>
        <span className="team away">← {awayTeam}</span>
      </div>
      <svg viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`} className="pitch" role="img"
        aria-label="Live pitch: where the ball is">
        <g className="camera" style={{ transform: view, transitionDuration: moment ? '1.1s' : '2.4s' }}>
          <PitchMarkings />
          <defs>
            {(['home', 'away'] as const).map((side) => (
              <linearGradient key={side} id={`lane-${side}`} x1={side === 'home' ? 0 : 1} x2={side === 'home' ? 1 : 0}>
                <stop offset="0%" stopColor="currentColor" stopOpacity="0" />
                <stop offset="100%" stopColor="currentColor" stopOpacity="0.55" />
              </linearGradient>
            ))}
            <radialGradient id="spot-fade">
              <stop offset="55%" stopColor="#000" />
              <stop offset="100%" stopColor="#fff" />
            </radialGradient>
          </defs>
          <Lanes stats={stats} homeTeam={homeTeam} awayTeam={awayTeam} colors={colors} />
          {showShot && (() => {
            const shot = showShot
            const [x, y] = drawn(shot.event.team, shot.event.location!)
            const xg = shot.moment.xg ?? 0
            const label = level === 'analyst' ? `xG ${xg.toFixed(2)}`
              : t(xg >= 0.3 ? 'big chance' : xg >= 0.1 ? 'half chance' : 'hard chance')
            const r = 1.5 + 9 * Math.sqrt(xg)
            return (
              <g key={`shot-${shot.event.id}`} className="shot-quality" style={{ color: colors[shot.event.team] }}>
                <circle cx={x} cy={y} r={r} />
                <text x={x} y={y + r + 3.6} className="shot-label">{label}</text>
              </g>
            )
          })()}

          {moves.map((m, i) => {
            if (!m.to) return null
            const age = (moves.length - 1 - i) / TRAIL
            const fresh = i === moves.length - 1 && m.kind !== 'carry' && m.complete
            return (
              <path key={`trail-${m.id}`} d={path(m)} pathLength={1}
                className={`trail ${m.home ? 'home' : 'away'} ${m.kind} ${m.complete ? '' : 'failed'} ${fresh ? 'fresh' : ''}`}
                style={{ opacity: 1 - age * 0.8, animationDuration: fresh ? `${FLIGHT[m.kind]}s` : undefined }} />
            )
          })}

          {goal && (
            <g key={`goal-${goal.id}`}>
              <rect x={goal.home ? 118 : 0} y={30} width={2} height={20} className="goal-flash" />
              <rect x={goal.home ? 120 : -2.4} y={36} width={2.4} height={8} fill="url(#net)"
                className={`net-bulge ${goal.home ? 'right' : 'left'}`} />
            </g>
          )}

          {latest && (
            <g className="player">
              {/* the passer, or the dribbler running with the ball */}
              <Shirt key={`${latest.player}-${latest.home}`} at={runner ? ball : latest.from}
                color={color(latest.home)} number={numberOf(latest.home, latest.player)} />
              <text x={latest.from[0]} y={latest.from[1] - 4.2} key={`n-${latest.id}`}>{surname(latest.player)}</text>
              {/* the receiver, there when the ball arrives */}
              {latest.kind === 'pass' && latest.complete && latest.recipient && latest.to && (
                <g key={`r-${latest.id}`}>
                  <Shirt at={latest.to} color={color(latest.home)} number={numberOf(latest.home, latest.recipient)}
                    className="arriving" delay={flight * 0.75} />
                  <text x={latest.to[0]} y={latest.to[1] + 6.4} className="recipient arriving"
                    style={{ animationDelay: `${flight * 0.75}s` }}>{surname(latest.recipient)}</text>
                </g>
              )}
            </g>
          )}

          <g className="ball" style={{ transform: `translate(${ball[0]}px, ${ball[1]}px)`, transitionDuration: `${flight}s` }}>
            <ellipse cx={0.5} cy={1.1} rx={1.4} ry={0.6} className="ball-shadow" />
            <g key={latest?.id} className={latest?.high ? 'ball-body lofted' : 'ball-body'}
              style={{ animationDuration: `${flight}s` }}>
              <circle r={2.2} className="ball-halo" filter="url(#ball-glow)" />
              <circle r={1.3} className="ball-core" />
            </g>
          </g>

          {focusOn && focus && (
            <g key={focusId} className="focus">
              {/* a telestrator spotlight: the rest of the pitch dims */}
              <mask id={`spot-${focusId}`}>
                <rect x={VIEW.x} y={VIEW.y} width={VIEW.w} height={VIEW.h} fill="#fff" />
                <circle cx={focusOn[0]} cy={focusOn[1]} r={11} fill="url(#spot-fade)" />
              </mask>
              <rect x={VIEW.x} y={VIEW.y} width={VIEW.w} height={VIEW.h} className="spot-dim"
                mask={`url(#spot-${focusId})`} />
              <circle cx={focusOn[0]} cy={focusOn[1]} r={4.2} className="focus-ring" />
              <circle cx={focusOn[0]} cy={focusOn[1]} r={0.9} className="focus-dot" />
              <g className="focus-tag" style={{ transform: `translate(${focusOn[0]}px, ${focusOn[1] - 8.5}px)` }}>
                <rect x={-9} y={-2.6} width={18} height={4.4} rx={2.2} />
                <text y={0.7}>{t.voice('Roy')} · {focus.minute}'</text>
              </g>
            </g>
          )}
        </g>
      </svg>
    </div>
  )
}
