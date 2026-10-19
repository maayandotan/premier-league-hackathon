import { useCallback, useEffect, useRef, useState } from 'react'
import type { CommentaryLine, FeedMessage, MatchInfo, MatchStats, RankedEvent } from './types'

export type FeedStatus = 'idle' | 'live' | 'ended' | 'error'

export interface FeedOptions {
  source: string // "demo" | "synthetic:<name>" | "statsbomb:<id>" (local only)
  speed: number
  start: number // minute
}

const MAX_EVENTS = 200 // a full match has thousands; keep the list light

/** Connects to the backend's live match WebSocket and collects events, commentary and stats. */
export function useMatchFeed({ source, speed, start }: FeedOptions) {
  const [status, setStatus] = useState<FeedStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<MatchInfo | null>(null)
  const [events, setEvents] = useState<RankedEvent[]>([])
  const [lines, setLines] = useState<CommentaryLine[]>([])
  const [stats, setStats] = useState<MatchStats | null>(null)
  const socket = useRef<WebSocket | null>(null)

  const begin = useCallback(() => {
    socket.current?.close()
    setEvents([])
    setLines([])
    setStats(null)
    setError(null)
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const query = new URLSearchParams({ source, speed: String(speed), start: String(start) })
    const ws = new WebSocket(`${protocol}://${location.host}/ws/match?${query}`)
    ws.onopen = () => setStatus('live')
    ws.onerror = () => setStatus('error')
    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data) as FeedMessage
      switch (data.type) {
        case 'match':
          setInfo(data.info)
          break
        case 'event':
          setEvents((prev) => [{ event: data.event, moment: data.moment }, ...prev].slice(0, MAX_EVENTS))
          break
        case 'commentary':
          setLines((prev) => [data.line, ...prev])
          break
        case 'stats':
          setStats(data.stats)
          break
        case 'end':
          setStats(data.stats)
          setStatus('ended')
          break
        case 'error':
          setError(data.message)
          setStatus('error')
      }
    }
    socket.current = ws
  }, [source, speed, start])

  useEffect(() => () => socket.current?.close(), [])

  return { status, error, info, events, lines, stats, start: begin }
}
