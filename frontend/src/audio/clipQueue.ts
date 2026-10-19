/**
 * The order and expiry rules of the commentary queue, kept apart from the Web Audio code so they
 * can be tested.
 * - Regular lines are dropped if they waited more than MAX_WAIT_MS (real time): late commentary
 *   describes a moment that has passed.
 * - An answer to a viewer's question is never thrown away by a big moment, goes ahead of regular
 *   lines, and stays valid until ANSWER_WINDOW_SECONDS of match time after the question was asked.
 */

export const MAX_WAIT_MS = 10_000
export const ANSWER_WINDOW_SECONDS = 8 * 60 // match clock, from the moment of the question

export interface Clip<T = unknown> {
  lineId: string
  buffer: T
  excitement: number
  receivedAt: number // performance.now() when it arrived
  askedAtClock?: number // set for answers: match clock (seconds) when the question was asked
}

/** "12:05" -> 725. */
export function parseClock(clock: string): number {
  const [minutes, seconds] = clock.split(':').map(Number)
  return minutes * 60 + (seconds || 0)
}

export function isAnswer(clip: Clip): boolean {
  return clip.askedAtClock !== undefined
}

export function isExpired(clip: Clip, nowMs: number, matchClock: number): boolean {
  if (clip.askedAtClock !== undefined) return matchClock - clip.askedAtClock > ANSWER_WINDOW_SECONDS
  return nowMs - clip.receivedAt > MAX_WAIT_MS
}

/**
 * Add a clip to the queue and return the new queue, plus whether the clip playing now should be
 * cut (a big moment cuts in).
 */
export function insertClip<T>(queue: Clip<T>[], clip: Clip<T>): { queue: Clip<T>[]; cut: boolean } {
  if (isAnswer(clip)) {
    // The viewer is waiting: after earlier answers, before regular commentary.
    const firstRegular = queue.findIndex((c) => !isAnswer(c))
    const at = firstRegular === -1 ? queue.length : firstRegular
    return { queue: [...queue.slice(0, at), clip, ...queue.slice(at)], cut: false }
  }
  if (clip.excitement >= 2) {
    // A big moment cuts in and clears regular lines; answers wait and play right after it.
    return { queue: [clip, ...queue.filter(isAnswer)], cut: true }
  }
  return { queue: [...queue, clip], cut: false }
}

/** Take the next clip that is still worth playing; returns it and the rest of the queue. */
export function takeNext<T>(queue: Clip<T>[], nowMs: number, matchClock: number):
  { clip: Clip<T> | undefined; queue: Clip<T>[]; dropped: number } {
  let dropped = 0
  let i = 0
  while (i < queue.length && isExpired(queue[i], nowMs, matchClock)) {
    dropped++
    i++
  }
  return { clip: queue[i], queue: queue.slice(i + 1), dropped }
}
