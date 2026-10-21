import { describe, expect, it } from 'vitest'
import {
  ANSWER, ANSWER_WINDOW_SECONDS, BIG_MOMENT, type Clip, MAX_WAIT_MS, REGULAR, insertClip, parseClock, takeNext,
} from './clipQueue'

const line = (lineId: string, excitement = 0, receivedAt = 0): Clip => ({ lineId, buffer: null, excitement, receivedAt })
const big = (lineId: string, excitement = 2): Clip => ({ ...line(lineId, excitement), bigMoment: true })
const answer = (lineId: string, askedAtClock = 0): Clip => ({ ...line(lineId), askedAtClock })
const ids = (queue: Clip[]) => queue.map((c) => c.lineId)

describe('parseClock', () => {
  it('turns m:ss into seconds', () => {
    expect(parseClock('12:05')).toBe(725)
    expect(parseClock('90:00')).toBe(5400)
  })
})

describe('insertClip', () => {
  it('puts an answer ahead of regular lines, after earlier answers', () => {
    const { queue } = insertClip([answer('q1'), line('a'), line('b')], answer('q2'))
    expect(ids(queue)).toEqual(['q1', 'q2', 'a', 'b'])
  })

  it('puts a big moment ahead of answers', () => {
    const { queue } = insertClip([answer('q1'), line('a')], big('red-card', 1))
    expect(ids(queue)).toEqual(['red-card', 'q1', 'a'])
  })

  it('a goal cuts an answer that is playing and clears regular lines, keeping waiting answers', () => {
    const result = insertClip([answer('q2'), line('a')], big('goal'), ANSWER)
    expect(result.cut).toBe(true)
    expect(ids(result.queue)).toEqual(['goal', 'q2'])
  })

  it('an exciting line that is not a big moment never cuts or jumps an answer', () => {
    const result = insertClip([answer('q2'), line('a')], line('corner', 2), ANSWER)
    expect(result.cut).toBe(false)
    expect(ids(result.queue)).toEqual(['q2', 'corner'])
  })

  it('an exciting regular line still cuts regular commentary', () => {
    expect(insertClip([], line('corner', 2), REGULAR).cut).toBe(true)
  })

  it('a calm big-moment line (analysis) waits its turn instead of cutting', () => {
    expect(insertClip([], big('analysis', 0), BIG_MOMENT).cut).toBe(false)
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
    expect(takeNext([answer('q1', asked)], hourLater, asked + ANSWER_WINDOW_SECONDS).clip?.lineId).toBe('q1')
  })

  it('drops an answer once 8 match minutes have passed since the question', () => {
    const asked = parseClock('30:00')
    const late = takeNext([answer('q1', asked)], 0, asked + ANSWER_WINDOW_SECONDS + 1)
    expect(late.clip).toBeUndefined()
    expect(late.dropped).toBe(1)
  })
})
