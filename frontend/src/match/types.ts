// Mirrors the backend's WebSocket messages (backend/app/main.py).

export interface MatchEvent {
  id: string
  period: number
  minute: number
  second: number
  type: string
  team: string
  player: string | null
  location: [number, number] | null
  details: Record<string, unknown>
}

export interface CommentaryLine {
  speaker: 'caller' | 'analyst'
  excitement: 0 | 1 | 2
  text: string
  event_id: string
}

export type FeedMessage =
  | { type: 'event'; event: MatchEvent }
  | { type: 'commentary'; line: CommentaryLine }
  | { type: 'end'; stats: Record<string, unknown> }
