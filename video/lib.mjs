// Recording helpers for the demo video: a page's pictures (Chrome's screencast, crisp at 1920x1080)
// and, for the live site, its sound (every clip the page's audio engine plays, with when it started).
import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

export const W = 1920
export const H = 1080
export const OUT = path.resolve('out')

export async function launch() {
  return chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] })
}

export function ffmpeg(...args) {
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...args], { stdio: 'inherit' })
}

/** Record what `page` shows while `act()` runs. Writes `<name>.mp4` (30 fps, no sound) and returns the
 * wall-clock time (seconds) of its first frame, so sounds can be lined up with it. */
export async function recordVideo(page, name, act) {
  const dir = path.join(OUT, `${name}-frames`)
  await fs.rm(dir, { recursive: true, force: true })
  await fs.mkdir(dir, { recursive: true })
  const client = await page.context().newCDPSession(page)
  const frames = []
  client.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    frames.push({ t: metadata.timestamp, data })
    await client.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
  })
  await client.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: W, maxHeight: H })
  await act()
  const end = Date.now() / 1000
  await client.send('Page.stopScreencast')
  // A frame comes only when the picture changes: each lasts until the next one.
  const lines = []
  for (const [i, frame] of frames.entries()) {
    const file = path.join(dir, `${String(i).padStart(6, '0')}.jpg`)
    await fs.writeFile(file, Buffer.from(frame.data, 'base64'))
    const until = i + 1 < frames.length ? frames[i + 1].t : end
    lines.push(`file '${file}'`, `duration ${Math.max(0.001, until - frame.t).toFixed(4)}`)
  }
  lines.push(`file '${path.join(dir, `${String(frames.length - 1).padStart(6, '0')}.jpg`)}'`)
  await fs.writeFile(path.join(dir, 'list.txt'), lines.join('\n'))
  ffmpeg('-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'), '-vf', `fps=30,scale=${W}:${H}`,
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', path.join(OUT, `${name}.mp4`))
  return { start: frames[0].t, end, frames: frames.length }
}

/** Before the page loads: note every sound the page's audio engine starts, and keep each commentary
 * clip's bytes. The crowd loop and the goal roar are our own files, so only their start times matter. */
export async function listenToAudio(page) {
  const clips = new Map() // id -> mp3 bytes
  const played = [] // { at (s, wall clock), kind: 'voice' | 'roar' | 'crowd', id, seconds }
  await page.exposeFunction('__saveClip', (id, b64) => { clips.set(id, Buffer.from(b64, 'base64')) })
  await page.exposeFunction('__played', (id, kind, seconds) => { played.push({ at: Date.now() / 1000, id, kind, seconds }) })
  await page.addInitScript(() => {
    let next = 0
    const tags = new WeakMap()
    const decode = AudioContext.prototype.decodeAudioData
    AudioContext.prototype.decodeAudioData = function (data, ...rest) {
      const bytes = new Uint8Array(data.slice(0))
      const wav = bytes[0] === 0x52 && bytes[1] === 0x49 // "RI"FF: our crowd files; else an MP3 line
      const id = `clip${next++}`
      if (!wav) {
        let text = ''
        for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
        window.__saveClip(id, btoa(text))
      }
      return decode.call(this, data, ...rest).then((buffer) => { tags.set(buffer, { id, wav }); return buffer })
    }
    const start = AudioBufferSourceNode.prototype.start
    AudioBufferSourceNode.prototype.start = function (...args) {
      const tag = this.buffer && tags.get(this.buffer)
      if (tag) window.__played(tag.id, tag.wav ? (this.loop ? 'crowd' : 'roar') : 'voice', this.buffer.duration)
      return start.apply(this, args)
    }
  })
  return { clips, played }
}

/** The page's soundtrack, lined up with its video: the roar and every commentary clip at the moment
 * the page started it. The crowd is left out: the edit lays one steady crowd under the whole video.
 * Writes `<name>-audio.wav`. */
export async function buildSoundtrack(name, video, audio, assets) {
  const length = video.end - video.start
  const inputs = ['-f', 'lavfi', '-t', length.toFixed(2), '-i', 'anullsrc=r=48000:cl=stereo']
  const mixes = ['[0:a]']
  let n = 1
  const add = (file, at, volume, loop = false, level = '') => {
    inputs.push(...(loop ? ['-stream_loop', '-1'] : []), '-i', file)
    const delay = Math.max(0, Math.round((at - video.start) * 1000))
    mixes.push(`[${n}:a]${level}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=${volume},adelay=${delay}|${delay},atrim=0:${length.toFixed(2)}[a${n}]`)
    n += 1
  }
  for (const sound of audio.played) {
    if (sound.kind === 'crowd') continue
    // the roar stays under the commentary: Davis's goal call must be heard over it
    if (sound.kind === 'roar') add(assets.roar, sound.at, 0.35)
    else if (audio.clips.has(sound.id)) {
      const file = path.join(OUT, `${name}-${sound.id}.mp3`)
      await fs.writeFile(file, audio.clips.get(sound.id))
      // every line equally clear: levelled on its own first (loudnorm misbehaves inside a big mix)
      const level = path.join(OUT, `${name}-${sound.id}-level.wav`)
      ffmpeg('-i', file, '-af', 'loudnorm=I=-16:TP=-1.5,aresample=48000', '-ac', '2', level)
      add(level, sound.at, 1.0)
    }
  }
  const labels = mixes.slice(1).map((m) => m.slice(m.lastIndexOf('[')))
  const filter = [...mixes.slice(1), `[0:a]${labels.join('')}amix=inputs=${labels.length + 1}:normalize=0,alimiter=limit=0.95[out]`]
  ffmpeg(...inputs, '-filter_complex', filter.join(';'), '-map', '[out]', '-t', length.toFixed(2),
    path.join(OUT, `${name}-audio.wav`))
}
