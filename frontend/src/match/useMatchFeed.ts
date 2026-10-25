import { useCallback, useEffect, useRef, useState } from 'react'
import { BroadcastAudio } from '../audio/broadcastAudio'
import { parseClock } from '../audio/clipQueue'
import type { CommentaryLine, FeedMessage, MatchInfo, MatchStats, RankedEvent, ViewerQuestion } from './types'

export type FeedStatus = 'idle' | 'live' | 'ended' | 'error'

export interface FeedOptions {
  source: string // "demo" | "synthetic:<name>" | "statsbomb:<id>" (local only)
  speed: number
  start: number // minute
  level: string // beginner | fan | analyst, at kick-off
}

const MAX_EVENTS = 200 // a full match has thousands; keep the list light

/** Connects to the backend's live match WebSocket and collects events, commentary and stats. */
export function useMatchFeed({ source, speed, start, level: initialLevel }: FeedOptions) {
  const [status, setStatus] = useState<FeedStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<MatchInfo | null>(null)
  const [events, setEvents] = useState<RankedEvent[]>([])
  const [lines, setLines] = useState<CommentaryLine[]>([])
  const [questions, setQuestions] = useState<ViewerQuestion[]>([])
  const [stats, setStats] = useState<MatchStats | null>(null)
  const socket = useRef<WebSocket | null>(null)
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const [audio] = useState(() => new BroadcastAudio(setSpeakingId))
  const [muted, setMuted] = useState(false)
  const [level, setLevelState] = useState(initialLevel)
  const [connected, setConnected] = useState(false)
  const askedAt = useRef(new Map<string, number>()) // question id -> match clock (s) when asked
  const answerOf = useRef(new Map<string, string>()) // answer line id -> question id
  const bigEvents = useRef(new Set<string>()) // event ids that beat viewers' questions
  const bigLines = useRef(new Set<string>()) // line ids about those events

  const begin = useCallback(() => {
    socket.current?.close()
    void audio.start() // inside the click: browsers only allow sound after a user gesture
    askedAt.current.clear()
    answerOf.current.clear()
    bigEvents.current.clear()
    bigLines.current.clear()
    audio.setMatchClock(0)
    setEvents([])
    setLines([])
    setQuestions([])
    setStats(null)
    setError(null)
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const query = new URLSearchParams({ source, speed: String(speed), start: String(start), level })
    const ws = new WebSocket(`${protocol}://${location.host}/ws/match?${query}`)
    let ended = false
    ws.onopen = () => {
      setStatus('live')
      setConnected(true)
    }
    ws.onerror = () => setStatus('error')
    // A dropped connection must show: otherwise the clock freezes and questions go nowhere.
    ws.onclose = () => {
      if (socket.current !== ws) return // an old match, closed by Restart
      setConnected(false)
      if (!ended) {
        setError('Lost the connection to the match. Press Kick off to watch again.')
        setStatus('error')
      }
    }
    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data) as FeedMessage
      switch (data.type) {
        case 'match':
          setInfo(data.info)
          setLevelState(data.level)
          break
        case 'level':
          setLevelState(data.level) // the server confirmed the change
          break
        case 'question':
          askedAt.current.set(data.id, parseClock(data.clock))
          setQuestions((prev) => [...prev, { id: data.id, text: data.text, clock: data.clock }])
          break
        case 'event':
          if (data.moment.kind === 'goal') audio.roar() // the crowd reacts before the caller does
          audio.setMatchClock(data.event.minute * 60 + data.event.second)
          if (data.moment.beats_questions) bigEvents.current.add(data.event.id)
          setEvents((prev) => [{ event: data.event, moment: data.moment }, ...prev].slice(0, MAX_EVENTS))
          break
        case 'audio':
        {
          // The text arrives before its audio, so its kind is already known here.
          const questionId = answerOf.current.get(data.line_id)
          void audio.enqueue(data.line_id, data.mp3, data.excitement, {
            askedAtClock: questionId ? askedAt.current.get(questionId) : undefined,
            bigMoment: bigLines.current.has(data.line_id),
          })
          break
        }
        case 'commentary':
          if (data.line.reply_to) answerOf.current.set(data.line.id, data.line.reply_to)
          if (bigEvents.current.has(data.line.event_id)) bigLines.current.add(data.line.id)
          setLines((prev) => [data.line, ...prev])
          break
        case 'stats':
          setStats(data.stats)
          break
        case 'end':
          ended = true
          setStats(data.stats)
          setStatus('ended')
          break
        case 'error':
          setError(data.message)
          setStatus('error')
      }
    }
    socket.current = ws
  }, [source, speed, start, level, audio])

  useEffect(() => () => {
    socket.current?.close()
    audio.stop()
  }, [audio])

  /** Change the level; mid-match it's sent to the server and the next line follows it. */
  const setLevel = useCallback((next: string) => {
    setLevelState(next)
    const ws = socket.current
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'set_level', level: next }))
  }, [])

  /** Ask the analyst a question; the match keeps going and the answer arrives as a line. */
  const ask = useCallback((text: string) => {
    const ws = socket.current
    if (text.trim() && ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'question', text }))
  }, [])

  /** While the viewer asks by voice, the commentators stay quiet. */
  const setListening = useCallback((on: boolean) => audio.setListening(on), [audio])

  const toggleMute = useCallback(() => {
    audio.setMuted(!muted)
    setMuted(!muted)
  }, [audio, muted])

  useEffect(() => {
    // Debugging aid in development: inspect played/dropped clips from the browser console.
    if (import.meta.env.DEV) Object.assign(window, { broadcastAudio: audio })
  }, [audio])

  return {
    status, error, info, events, lines, questions, stats, muted, speakingId, level, setLevel, ask, setListening,
    toggleMute, start: begin, connected,
  }
}
