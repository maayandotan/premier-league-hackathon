import { useCallback, useEffect, useRef, useState } from 'react'
import type { CommentaryLine, FeedMessage, MatchEvent } from './types'

export type FeedStatus = 'idle' | 'live' | 'ended' | 'error'

/** Connects to the backend's live match WebSocket and collects events and commentary. */
export function useMatchFeed(speed = 1) {
  const [status, setStatus] = useState<FeedStatus>('idle')
  const [events, setEvents] = useState<MatchEvent[]>([])
  const [lines, setLines] = useState<CommentaryLine[]>([])
  const socket = useRef<WebSocket | null>(null)

  const start = useCallback(() => {
    socket.current?.close()
    setEvents([])
    setLines([])
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${location.host}/ws/match?speed=${speed}`)
    ws.onopen = () => setStatus('live')
    ws.onerror = () => setStatus('error')
    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data) as FeedMessage
      if (data.type === 'event') setEvents((prev) => [...prev, data.event])
      else if (data.type === 'commentary') setLines((prev) => [...prev, data.line])
      else setStatus('ended')
    }
    socket.current = ws
  }, [speed])

  useEffect(() => () => socket.current?.close(), [])

  return { status, events, lines, start }
}
