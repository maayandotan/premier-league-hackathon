const LEVELS = [
  { id: 'beginner', label: 'Beginner', hint: 'New to football' },
  { id: 'fan', label: 'Fan', hint: 'Knows the game' },
  { id: 'analyst', label: 'Analyst', hint: 'Wants the details' },
] as const

export type Level = (typeof LEVELS)[number]['id']

/** "Commentary at my level". Not wired to the agents yet (#15). */
export function LevelPicker({ value, onChange }: { value: Level; onChange: (level: Level) => void }) {
  return (
    <div className="level-picker" role="radiogroup" aria-label="Commentary level">
      {LEVELS.map((level) => (
        <button key={level.id} role="radio" aria-checked={value === level.id} title={level.hint}
          className={value === level.id ? 'active' : ''} onClick={() => onChange(level.id)}>
          {level.label}
        </button>
      ))}
    </div>
  )
}
