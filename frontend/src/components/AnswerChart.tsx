import { useT } from '../i18n'
import type { AnswerChartSpec } from '../match/types'

const RESULT_COLORS = { won: '#22c55e', drawn: '#94a3b8', lost: '#f43f5e' } as const
const W = 400 // the charts' drawing width; they scale to the card

/** The chart that came with Roy's answer, drawn from the data the backend built (charts.py). */
export function AnswerChart({ chart, colors }: { chart: AnswerChartSpec; colors?: Record<string, string> }) {
  if (chart.type === 'team_by_goals') return <TeamByGoals chart={chart} />
  if (chart.type === 'player_by_time') return <PlayerByTime chart={chart} />
  return <XgRace chart={chart} colors={colors ?? {}} />
}

/** A club's results grouped by goals scored: one stacked bar per group, won / drawn / lost. */
function TeamByGoals({ chart }: { chart: Extract<AnswerChartSpec, { type: 'team_by_goals' }> }) {
  const t = useT()
  const most = Math.max(1, ...chart.groups.map((_, i) => chart.won[i] + chart.drawn[i] + chart.lost[i]))
  const results = ['won', 'drawn', 'lost'] as const
  return (
    <figure className="answer-chart">
      <figcaption>
        <strong>{t('{team}: results by goals scored', { team: chart.team })}</strong>
        <span>{t('{n} league matches this season', { n: chart.matches })}</span>
      </figcaption>
      <div className="ac-rows">
        {chart.groups.map((group, i) => {
          const total = chart.won[i] + chart.drawn[i] + chart.lost[i]
          return (
            <div key={group} className="ac-row">
              <span className="ac-label">{t('Scored {n}', { n: group })}</span>
              <div className="ac-track">
                {results.map((r) => chart[r][i] > 0 && (
                  <span key={r} className="ac-seg" title={`${t(r)}: ${chart[r][i]}`}
                    style={{ width: `${(chart[r][i] / most) * 100}%`, background: RESULT_COLORS[r] }}>
                    {chart[r][i]}
                  </span>
                ))}
                {total === 0 && <span className="ac-none">{t('no matches')}</span>}
              </div>
            </div>
          )
        })}
      </div>
      <Legend items={results.map((r) => [t(r), RESULT_COLORS[r]])} />
    </figure>
  )
}

/** A player's shots and goals by 15-minute window, and his penalties along the same clock. */
function PlayerByTime({ chart }: { chart: Extract<AnswerChartSpec, { type: 'player_by_time' }> }) {
  const t = useT()
  const H = 120
  const top = Math.max(1, ...chart.shots)
  const slot = W / chart.windows.length
  const bar = slot * 0.56
  const y = (v: number) => H - (v / top) * (H - 18)
  const scored = chart.penalties.filter((p) => p.scored).length
  return (
    <figure className="answer-chart">
      <figcaption>
        <strong>{t('{player}: shots and goals by match time', { player: chart.player })}</strong>
        <span>{t('{shots} shots, {goals} goals this season', {
          shots: chart.shots.reduce((a, b) => a + b, 0), goals: chart.goals.reduce((a, b) => a + b, 0) })}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H + 40}`} role="img" aria-label={t('Shots and goals by match time')}>
        {chart.windows.map((label, i) => {
          const x = i * slot + (slot - bar) / 2
          const rate = chart.shots[i] ? Math.round((100 * chart.goals[i]) / chart.shots[i]) : null
          return (
            <g key={label}>
              <title>{`${label}: ${chart.goals[i]}/${chart.shots[i]}${rate === null ? '' : ` (${rate}%)`}`}</title>
              <rect x={x} y={y(chart.shots[i])} width={bar} height={H - y(chart.shots[i])} rx={3} className="ac-shots" />
              <rect x={x} y={y(chart.goals[i])} width={bar} height={H - y(chart.goals[i])} rx={3} className="ac-goals" />
              <text x={x + bar / 2} y={y(chart.shots[i]) - 4} textAnchor="middle" className="ac-value">
                {chart.shots[i] ? `${chart.goals[i]}/${chart.shots[i]}` : ''}
              </text>
              <text x={x + bar / 2} y={H + 14} textAnchor="middle" className="ac-axis">{label}</text>
            </g>
          )
        })}
        <line x1={0} x2={W} y1={H} y2={H} className="ac-base" />
        {chart.penalties.map((p, i) => {
          const minute = Math.min(p.minute, 95)
          return (
            <g key={i}>
              <title>{`${t('Penalty')} ${p.minute}': ${t(p.scored ? 'scored' : 'missed')}`}</title>
              <circle cx={(minute / 95) * W} cy={H + 30} r={5} className={p.scored ? 'ac-pen-in' : 'ac-pen-out'} />
            </g>
          )
        })}
      </svg>
      <Legend items={[[t('Shots'), 'var(--ac-shots)'], [t('Goals'), 'var(--ac-goals)'],
        [`${t('Penalties')}: ${scored}/${chart.penalties.length}`, 'var(--ac-goals)', 'dot']]} />
    </figure>
  )
}

/** This match: each team's expected goals adding up, goals marked on the line. */
function XgRace({ chart, colors }: { chart: Extract<AnswerChartSpec, { type: 'xg_race' }>; colors: Record<string, string> }) {
  const t = useT()
  const H = 130
  const teams = [chart.home, chart.away]
  const end = Math.max(90, chart.minute)
  const top = Math.max(1, ...teams.flatMap((team) => chart.points[team].map(([, v]) => v)))
  const x = (m: number) => 30 + (m / end) * (W - 80)
  const y = (v: number) => H - (v / top) * (H - 12)
  const color = (team: string, i: number) => colors[team] ?? (i ? '#f43f5e' : '#3b82f6')
  const step = (team: string) => chart.points[team].reduce((path, [m, v], i, all) =>
    i ? `${path} H${x(m).toFixed(1)} V${y(v).toFixed(1)}` : `M${x(m).toFixed(1)} ${y(all[0][1]).toFixed(1)}`, '')
  const valueAt = (team: string, m: number) => [...chart.points[team]].reverse().find(([pm]) => pm <= m)?.[1] ?? 0
  return (
    <figure className="answer-chart">
      <figcaption>
        <strong>{t('Expected goals adding up')}</strong>
        <span>{t('This match, to {m}\'', { m: chart.minute })}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H + 22}`} role="img" aria-label={t('Expected goals adding up')}>
        {[0, 45, 90].map((m) => (
          <text key={m} x={x(m)} y={H + 16} textAnchor="middle" className="ac-axis">{m}'</text>
        ))}
        <line x1={x(0)} x2={x(end)} y1={H} y2={H} className="ac-base" />
        {teams.map((team, i) => (
          <g key={team}>
            <path d={step(team)} fill="none" stroke={color(team, i)} strokeWidth={2.2}
              strokeDasharray={i ? '5 4' : undefined} />
            <text x={x(chart.minute) + 6} y={y(valueAt(team, chart.minute)) + 4} className="ac-value">
              {valueAt(team, chart.minute).toFixed(2)}
            </text>
          </g>
        ))}
        {chart.goals.map((g, i) => (
          <circle key={i} cx={x(g.minute)} cy={y(valueAt(g.team, g.minute))} r={5} fill={color(g.team, teams.indexOf(g.team))}
            className="ac-goal-dot"><title>{`${t('Goal')} ${g.team} ${g.minute}'`}</title></circle>
        ))}
      </svg>
      <Legend items={teams.map((team, i) => [team, color(team, i), i ? 'dashed' : 'line'])} />
    </figure>
  )
}

function Legend({ items }: { items: (string[])[] }) {
  return (
    <div className="ac-legend">
      {items.map(([label, color, kind]) => (
        <span key={label}><i className={`ac-key ${kind ?? 'box'}`} style={{ background: kind === 'dashed' ? undefined : color,
          borderColor: color }} />{label}</span>
      ))}
    </div>
  )
}
