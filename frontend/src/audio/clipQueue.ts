/**
 * The order and expiry rules of the commentary queue, kept apart from the Web Audio code so they
 * can be tested.
 *
 * Three tiers, highest first:
 *   0. Big moments: lines about an event the backend ranked beats_questions (a goal, a red card,
 *      a penalty, a real threat on goal, a free kick within 23 m).
 *   1. Answers to the viewer's questions: the viewer is waiting, so they beat everything else.
 *   2. All other commentary.
 * A clip waits behind clips of its own tier or higher. An exciting clip (excitement 2) cuts the
 * clip playing now only if that clip is of the same tier or lower, and clears waiting tier-2 lines.
 *
 * Expiry: tier-2 and big-moment lines are dropped after MAX_WAIT_MS (real time): late commentary
 * describes a moment that has passed. An answer stays valid until ANSWER_WINDOW_SECONDS of match
 * time after the question was asked.
 */

export const MAX_WAIT_MS = 10_000
export const ANSWER_WINDOW_SECONDS = 8 * 60 // match clock, from the moment of the question

export const BIG_MOMENT = 0
export const ANSWER = 1
export const REGULAR = 2
export type Tier = typeof BIG_MOMENT | typeof ANSWER | typeof REGULAR

export interface Clip<T = unknown> {
  lineId: string
  buffer: T
  excitement: number
  receivedAt: number // performance.now() when it arrived
  askedAtClock?: number // set for answers: match clock (seconds) when the question was asked
  bigMoment?: boolean // the line is about an event that beats viewers' questions
}

/** "12:05" -> 725. */
export function parseClock(clock: string): number {
  const [minutes, seconds] = clock.split(':').map(Number)
  return minutes * 60 + (seconds || 0)
}

export function tierOf(clip: Clip): Tier {
  if (clip.bigMoment) return BIG_MOMENT
  if (clip.askedAtClock !== undefined) return ANSWER
  return REGULAR
}

export function isExpired(clip: Clip, nowMs: number, matchClock: number): boolean {
  if (clip.askedAtClock !== undefined) return matchClock - clip.askedAtClock > ANSWER_WINDOW_SECONDS
  return nowMs - clip.receivedAt > MAX_WAIT_MS
}

/**
 * Add a clip to the queue. currentTier is the tier of the clip playing now (undefined if none).
 * Returns the new queue and whether the clip playing now should be cut.
 */
export function insertClip<T>(queue: Clip<T>[], clip: Clip<T>, currentTier?: Tier):
  { queue: Clip<T>[]; cut: boolean } {
  const tier = tierOf(clip)
  const exciting = clip.excitement >= 2
  const kept = exciting ? queue.filter((c) => tierOf(c) !== REGULAR) : queue
  let at = kept.length
  while (at > 0 && tierOf(kept[at - 1]) > tier) at--
  const cut = exciting && currentTier !== undefined && currentTier >= tier
  return { queue: [...kept.slice(0, at), clip, ...kept.slice(at)], cut }
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
