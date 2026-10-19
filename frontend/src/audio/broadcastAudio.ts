/**
 * The broadcast's sound, with the Web Audio API (#20):
 * - a crowd bed that loops all match and dips while someone is speaking
 * - a goal roar, started the moment the goal event arrives (before the commentary)
 * - a queue of commentary clips: played in order, big moments (excitement 2) cut in,
 *   and clips that waited too long are dropped rather than played late
 * - an answer to the viewer's question goes ahead of regular lines, survives big-moment cuts and
 *   stays valid for 8 minutes of match time after the question (rules in clipQueue.ts)
 * - while the viewer is asking a question by voice, the commentators fall silent and the crowd
 *   drops right down (so they can be heard, and the mic doesn't pick up the commentary)
 * Crowd audio: "Free Crowd Cheering Sounds" by Gregor Quendel, CC BY 4.0 (assets/audio/CREDITS.md).
 */

import { type Clip, insertClip, takeNext } from './clipQueue'

const CROWD_LEVEL = 0.35
const CROWD_UNDER_VOICE = 0.18
const CROWD_WHILE_LISTENING = 0.05
const ROAR_LEVEL = 0.9

type QueuedClip = Clip<AudioBuffer>

function decodeBase64(b64: string): ArrayBuffer {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
  return bytes.buffer
}

export class BroadcastAudio {
  private ctx: AudioContext | null = null
  private crowdGain: GainNode | null = null
  private voiceGain: GainNode | null = null
  private roarBuffer: AudioBuffer | null = null
  private crowdSource: AudioBufferSourceNode | null = null
  private current: AudioBufferSourceNode | null = null
  private queue: QueuedClip[] = []
  private listening = false
  muted = false
  played = 0 // for debugging: clips actually played
  dropped = 0 // clips skipped because they arrived too late
  private matchClock = 0 // seconds, from the latest event: answers expire on match time

  /** The match clock (seconds) of the latest event; 0 at kick-off. */
  setMatchClock(seconds: number): void {
    this.matchClock = seconds
  }

  /** onSpeaking is told which line is being spoken, or null when nobody is speaking. */
  private readonly onSpeaking: (lineId: string | null) => void

  constructor(onSpeaking: (lineId: string | null) => void = () => {}) {
    this.onSpeaking = onSpeaking
  }

  /** Must be called from a click: browsers only allow sound after a user gesture. */
  async start(): Promise<void> {
    this.stop()
    const ctx = new AudioContext()
    this.ctx = ctx
    this.crowdGain = ctx.createGain()
    this.voiceGain = ctx.createGain()
    this.crowdGain.connect(ctx.destination)
    this.voiceGain.connect(ctx.destination)
    this.applyMute()

    const load = async (name: string) =>
      ctx.decodeAudioData(await (await fetch(`/static/audio/${name}`)).arrayBuffer())
    const [crowd, roar] = await Promise.all([load('crowd_ambience_loop.wav'), load('crowd_goal_roar.wav')])
    if (this.ctx !== ctx) return // stopped while loading
    this.roarBuffer = roar
    this.crowdSource = ctx.createBufferSource()
    this.crowdSource.buffer = crowd
    this.crowdSource.loop = true
    this.crowdSource.connect(this.crowdGain)
    this.crowdGain.gain.value = CROWD_LEVEL
    this.crowdSource.start()
  }

  stop(): void {
    this.queue = []
    this.current = null
    this.onSpeaking(null)
    void this.ctx?.close()
    this.ctx = null
  }

  setMuted(muted: boolean): void {
    this.muted = muted
    this.applyMute()
  }

  /** The viewer is asking by voice: silence the commentators until they're done. */
  setListening(on: boolean): void {
    this.listening = on
    if (on) {
      this.cutCurrent() // stop mid-sentence; lines that arrive meanwhile wait in the queue
      this.onSpeaking(null)
      this.duckCrowd(false)
    } else {
      this.duckCrowd(false)
      if (!this.current) this.playNext() // late clips are dropped there (answers wait up to 8 min)
    }
  }

  /** The stadium reacts to the goal itself, a second before the caller does. */
  roar(): void {
    if (!this.ctx || !this.roarBuffer) return
    const source = this.ctx.createBufferSource()
    const gain = this.ctx.createGain()
    gain.gain.value = ROAR_LEVEL
    source.buffer = this.roarBuffer
    source.connect(gain).connect(this.crowdGain!)
    source.start()
  }

  /**
   * A commentary clip arrived (base64 MP3). askedAtClock (match clock in seconds when the viewer
   * asked) marks the clip as an answer to that question.
   */
  async enqueue(lineId: string, mp3: string, excitement: number, askedAtClock?: number): Promise<void> {
    if (!this.ctx) return
    const buffer = await this.ctx.decodeAudioData(decodeBase64(mp3))
    const clip: QueuedClip = { lineId, buffer, excitement, receivedAt: performance.now(), askedAtClock }
    const { queue, cut } = insertClip(this.queue, clip)
    this.queue = queue
    if (cut) this.cutCurrent()
    if (!this.current && !this.listening) this.playNext()
  }

  private playNext(): void {
    const ctx = this.ctx
    if (!ctx || this.listening) return
    const next = takeNext(this.queue, performance.now(), this.matchClock)
    this.queue = next.queue
    this.dropped += next.dropped // too late to be relevant
    const clip = next.clip
    if (!clip) {
      this.duckCrowd(false)
      this.onSpeaking(null)
      return
    }
    const source = ctx.createBufferSource()
    source.buffer = clip.buffer
    source.connect(this.voiceGain!)
    source.onended = () => {
      if (this.current === source) {
        this.current = null
        this.playNext()
      }
    }
    this.current = source
    this.duckCrowd(true)
    this.onSpeaking(clip.lineId)
    source.start()
    this.played++
  }

  private cutCurrent(): void {
    const playing = this.current
    this.current = null
    playing?.stop()
  }

  private duckCrowd(speaking: boolean): void {
    if (!this.ctx || !this.crowdGain) return
    const target = this.listening ? CROWD_WHILE_LISTENING : speaking ? CROWD_UNDER_VOICE : CROWD_LEVEL
    this.crowdGain.gain.setTargetAtTime(target, this.ctx.currentTime, 0.25)
  }

  /** Muting pauses the whole sound clock; clips that wait too long are dropped when it resumes. */
  private applyMute(): void {
    if (this.ctx) void (this.muted ? this.ctx.suspend() : this.ctx.resume())
  }
}
