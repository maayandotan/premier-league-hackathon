import { BASICS_ES, useT } from '../i18n'

/** For beginners: the handful of things worth knowing to follow a match. Our own words. */
const BASICS = [
  ['Goal', 'The whole ball crosses the line between the posts. The team with more goals at the end wins.'],
  ['Free kick', 'After a foul, the fouled team restarts with a kick from that spot. Near the goal, they can shoot.'],
  ['Penalty', 'A foul by a defender in their own box: one shot from 11 metres, just the goalkeeper to beat.'],
  ['Offside', 'An attacker can\'t wait behind the last defender for a pass. Level with him is fine.'],
  ['Yellow and red cards', 'A yellow is a warning. Two yellows, or one red, and the player leaves: his team plays with 10.'],
  ['Corner', 'When a defender knocks the ball over their own goal line, the attackers kick it in from the corner.'],
]

export function BeginnerGuide() {
  const t = useT()
  return (
    <section className="card guide" aria-label={t('Football basics')}>
      <h2>{t('Football basics')}</h2>
      <dl>
        {(t.lang === 'es' ? BASICS_ES : BASICS).map(([term, text]) => (
          <div key={term}><dt>{term}</dt><dd>{text}</dd></div>
        ))}
      </dl>
      <p className="stat-note">{t('Ask Roy about anything else, any time: the match keeps going.')}</p>
    </section>
  )
}
