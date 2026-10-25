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
  pass?: { recipient?: string; outcome: string; end_location?: [number, number]; cross?: boolean }
  carry?: { end_location?: [number, number] }
  shot?: { outcome: string; type?: string; end_location?: number[] }
  card?: string
  foul?: { card?: string }
}

export interface Moment {
  score: number // 0 routine ... 10 goal
  reason: string
  kind: string
  quiet: boolean
  beats_questions?: boolean // heard before a viewer's answer (goal, red card, penalty, big chance, close free kick)
}

export interface RankedEvent {
  event: MatchEvent
  moment: Moment
}

export interface Player {
  name: string
  jersey_number?: number
  position?: string
  starter?: boolean
}

export interface MatchInfo {
  id: string
  source: string
  competition?: string
  home: TeamInfo
  away: TeamInfo
}

export interface TeamInfo {
  name: string
  code?: string
  color?: string
  players?: Player[]
}

export interface TableRow {
  position: number
  team: string
  played: number
  won: number
  drawn: number
  lost: number
  goal_difference: number
  points: number
  form: string // last 5, oldest first: "WDLWW"
}

export interface LeagueFixture {
  home: string
  away: string
  source: string
  result: string | null
}

export interface Club {
  name: string
  code: string
  color: string
  secondary: string
}

export interface ClubSeason extends TableRow {
  captain: string
  top_scorers: { player: string; goals: number }[]
  top_assisters: { player: string; assists: number }[]
}

export interface League {
  clubs: Club[]
  league: string
  matchday: number
  fixtures: LeagueFixture[]
  table: TableRow[]
  top_scorers: { player: string; team: string; goals: number }[]
}

export interface CommentaryLine {
  id: string
  speaker: 'caller' | 'analyst'
  excitement: 0 | 1 | 2
  text: string
  event_id: string
  source: 'model' | 'template'
  level: string // the viewer level it was written for
  reply_to?: string | null // the viewer question it answers
}

export interface ViewerQuestion {
  id: string
  text: string
  clock: string
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
  patterns?: Record<string, { last_15_minutes: string[]; final_third_entries_all_match: ByTeam<number> }>
}

export interface XgPoint {
  minute: number
  xg: ByTeam<number>
}

export type FeedMessage =
  | { type: 'match'; info: MatchInfo; audio: boolean; level: string }
  | { type: 'level'; level: string }
  | { type: 'team'; team: string | null }
  | { type: 'question'; id: string; text: string; clock: string }
  | { type: 'event'; event: MatchEvent; moment: Moment }
  | { type: 'commentary'; line: CommentaryLine }
  | { type: 'audio'; line_id: string; excitement: number; mp3: string }
  | { type: 'stats'; stats: MatchStats }
  | { type: 'end'; stats: MatchStats }
  | { type: 'error'; message: string }
