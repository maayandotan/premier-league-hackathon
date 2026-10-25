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
  return (
    <section className="card guide" aria-label="Football basics">
      <h2>Football basics</h2>
      <dl>
        {BASICS.map(([term, text]) => (
          <div key={term}><dt>{term}</dt><dd>{text}</dd></div>
        ))}
      </dl>
      <p className="stat-note">Ask Sonia about anything else, any time: the match keeps going.</p>
    </section>
  )
}
