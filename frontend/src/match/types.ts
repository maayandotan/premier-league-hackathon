// Mirrors the backend's WebSocket messages (backend/app/main.py) and event schema (docs/event-schema.md).

export interface MatchEvent {
  id: string
  index: number
  period: number
  minute: number
  second: number
  type: string
  team: string
  player?: string
  location?: [number, number]
  pass?: { recipient?: string; outcome: string }
  shot?: { outcome: string; type?: string }
  card?: string
  foul?: { card?: string }
}

export interface Moment {
  score: number // 0 routine ... 10 goal
  reason: string
  kind: string
  quiet: boolean
}

export interface RankedEvent {
  event: MatchEvent
  moment: Moment
}

export interface MatchInfo {
  id: string
  source: string
  competition?: string
  home: { name: string }
  away: { name: string }
}

export interface CommentaryLine {
  speaker: 'caller' | 'analyst'
  excitement: 0 | 1 | 2
  text: string
  event_id: string
}

export type ByTeam<T> = Record<string, T>

export interface MatchStats {
  minute: number
  score: ByTeam<number>
  shootout: ByTeam<number> | null
  shots: ByTeam<number>
  xg: ByTeam<number>
  possession: ByTeam<number>
  possession_last_10: ByTeam<number>
  momentum: { value: number; leader: string | null }
  tempo: { possession_changes_per_min: number; label: string }
  progressive_passes: ByTeam<number>
}

export type FeedMessage =
  | { type: 'match'; info: MatchInfo }
  | { type: 'event'; event: MatchEvent; moment: Moment }
  | { type: 'commentary'; line: CommentaryLine }
  | { type: 'stats'; stats: MatchStats }
  | { type: 'end'; stats: MatchStats }
  | { type: 'error'; message: string }
