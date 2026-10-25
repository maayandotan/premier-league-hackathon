import { useState } from 'react'
import type { MatchInfo, XgPoint } from '../match/types'

const W = 560
const H = 200
const PAD = { left: 34, right: 64, top: 12, bottom: 26 }
const NEUTRAL = '#cbd5e1' // the away line's colour when the two clubs' colours are too alike

/** OKLab distance x100 between two colours (what the palette validator measures). */
function deltaE(a: string, b: string): number {
  const lab = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * bl)
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * bl)
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * bl)
    return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
      1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
      0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s]
  }
  const [x, y] = [lab(a), lab(b)]
  return 100 * Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2])
}

/** Each team's expected goals adding up over the match: who has been creating the better chances,
 * and when. Two lines on one axis; the away line is dashed and both are labelled at their ends, so
 * colour is never the only way to tell them apart. */
export function XgTimeline({ info, history }: { info: MatchInfo; history: XgPoint[] }) {
  const [hover, setHover] = useState<XgPoint | null>(null)
  const home = { name: info.home.name, code: info.home.code ?? info.home.name.slice(0, 3).toUpperCase(),
    color: info.home.color ?? '#3b82f6' }
  const awayColor = info.away.color ?? '#f43f5e'
  const away = { name: info.away.name, code: info.away.code ?? info.away.name.slice(0, 3).toUpperCase(),
    color: deltaE(home.color, awayColor) < 15 ? NEUTRAL : awayColor }

  const lastMinute = Math.max(90, history[history.length - 1]?.minute ?? 0)
  const top = Math.max(1, Math.ceil(Math.max(0, ...history.flatMap((p) => [p.xg[home.name], p.xg[away.name]])) * 2) / 2)
  const x = (minute: number) => PAD.left + (minute / lastMinute) * (W - PAD.left - PAD.right)
  const y = (xg: number) => H - PAD.bottom - (xg / top) * (H - PAD.top - PAD.bottom)
  const path = (team: string) => history.map((p, i) => `${i ? 'L' : 'M'}${x(p.minute).toFixed(1)},${y(p.xg[team]).toFixed(1)}`).join('')
  const last = history[history.length - 1]
  const ticks = Array.from({ length: Math.round(top / 0.5) + 1 }, (_, i) => i * 0.5)

  const onMove = (event: React.MouseEvent<SVGRectElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const minute = ((event.clientX - box.left) / box.width) * lastMinute
    setHover(history.reduce((best, p) => (Math.abs(p.minute - minute) < Math.abs(best.minute - minute) ? p : best),
      history[0]))
  }

  return (
    <section className="card xg-timeline" aria-label="Expected goals over the match">
      <h2>Expected goals <span className="league-sub">adding up over the match</span></h2>
      <div className="xg-legend" aria-hidden="true">
        <span><i style={{ background: home.color }} />{home.name}</span>
        <span><i className="dashed" style={{ borderColor: away.color }} />{away.name}</span>
      </div>
      {history.length < 2 ? (
        <p className="empty">The chart fills in as the match goes on.</p>
      ) : (
        <div className="xg-plot">
          <svg viewBox={`0 0 ${W} ${H}`} role="img"
            aria-label={`Expected goals: ${home.name} ${last.xg[home.name].toFixed(2)}, ${away.name} ${last.xg[away.name].toFixed(2)}`}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className="xg-grid" />
                <text x={PAD.left - 6} y={y(t) + 3} className="xg-axis" textAnchor="end">{t.toFixed(1)}</text>
              </g>
            ))}
            {[0, 45, 90].filter((m) => m <= lastMinute).map((m) => (
              <text key={m} x={x(m)} y={H - 8} className="xg-axis" textAnchor="middle">{m}'</text>
            ))}
            <path d={path(home.name)} fill="none" stroke={home.color} strokeWidth={2} strokeLinejoin="round" />
            <path d={path(away.name)} fill="none" stroke={away.color} strokeWidth={2} strokeDasharray="5 4"
              strokeLinejoin="round" />
            <text x={x(last.minute) + 6} y={y(last.xg[home.name]) + 4} className="xg-label">
              {home.code} {last.xg[home.name].toFixed(2)}
            </text>
            <text x={x(last.minute) + 6} y={y(last.xg[away.name]) + 4} className="xg-label">
              {away.code} {last.xg[away.name].toFixed(2)}
            </text>
            {hover && (
              <g pointerEvents="none">
                <line x1={x(hover.minute)} x2={x(hover.minute)} y1={PAD.top} y2={H - PAD.bottom} className="xg-cross" />
                <circle cx={x(hover.minute)} cy={y(hover.xg[home.name])} r={4} fill={home.color} className="xg-dot" />
                <circle cx={x(hover.minute)} cy={y(hover.xg[away.name])} r={4} fill={away.color} className="xg-dot" />
              </g>
            )}
            <rect x={PAD.left} y={PAD.top} width={W - PAD.left - PAD.right} height={H - PAD.top - PAD.bottom}
              fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
          </svg>
          {hover && (
            <div className="xg-tip" style={{ left: `${(x(hover.minute) / W) * 100}%` }}>
              <strong>{hover.minute}'</strong>
              <span>{home.code} {hover.xg[home.name].toFixed(2)}</span>
              <span>{away.code} {hover.xg[away.name].toFixed(2)}</span>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
