import { describe, expect, it } from 'vitest'
import { ANSWER_WINDOW_SECONDS, type Clip, MAX_WAIT_MS, insertClip, parseClock, takeNext } from './clipQueue'

const line = (lineId: string, excitement = 0, receivedAt = 0): Clip => ({ lineId, buffer: null, excitement, receivedAt })
const answer = (lineId: string, askedAtClock: number, receivedAt = 0): Clip =>
  ({ ...line(lineId, 0, receivedAt), askedAtClock })

describe('parseClock', () => {
  it('turns m:ss into seconds', () => {
    expect(parseClock('12:05')).toBe(725)
    expect(parseClock('90:00')).toBe(5400)
  })
})

describe('insertClip', () => {
  it('puts an answer ahead of regular lines, after earlier answers', () => {
    let queue = [answer('q1-answer', 0), line('a'), line('b')]
    queue = insertClip(queue, answer('q2-answer', 0)).queue
    expect(queue.map((c) => c.lineId)).toEqual(['q1-answer', 'q2-answer', 'a', 'b'])
  })

  it('a big moment clears regular lines but keeps answers, right after it', () => {
    const result = insertClip([line('a'), answer('q1-answer', 0), line('b')], line('goal', 2))
    expect(result.cut).toBe(true)
    expect(result.queue.map((c) => c.lineId)).toEqual(['goal', 'q1-answer'])
  })
})

describe('takeNext', () => {
  it('drops regular lines that waited over 10 s of real time', () => {
    const { clip, dropped } = takeNext([line('old', 0, 0), line('fresh', 0, MAX_WAIT_MS)], MAX_WAIT_MS + 1, 0)
    expect(dropped).toBe(1)
    expect(clip?.lineId).toBe('fresh')
  })

  it('keeps an answer for up to 8 minutes of match time, whatever the real time', () => {
    const asked = parseClock('30:00')
    const hourLater = 60 * 60 * 1000
    const inWindow = takeNext([answer('q1-answer', asked)], hourLater, asked + ANSWER_WINDOW_SECONDS)
    expect(inWindow.clip?.lineId).toBe('q1-answer')
  })

  it('drops an answer once 8 match minutes have passed since the question', () => {
    const asked = parseClock('30:00')
    const late = takeNext([answer('q1-answer', asked)], 0, asked + ANSWER_WINDOW_SECONDS + 1)
    expect(late.clip).toBeUndefined()
    expect(late.dropped).toBe(1)
  })
})
