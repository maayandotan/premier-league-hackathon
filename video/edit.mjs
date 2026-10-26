// Cuts the recorded scenes and live takes into the demo video, under 2 minutes, and lays the narration
// over it. Run after scenes.mjs and live.mjs:   node edit.mjs [narration folder]
// Without a narration folder (or with missing lines) it renders a draft without those lines.
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { ffmpeg, OUT } from './lib.mjs'

const NARRATION = process.argv[2] ?? path.join(os.homedir(), 'Desktop', 'your-call-narration2')
const main = JSON.parse(fs.readFileSync(path.join(OUT, 'live-main.json'))).marks
const beginnerTake = JSON.parse(fs.readFileSync(path.join(OUT, 'live-beginner.json')))
const beginner = beginnerTake.marks
// the first commentary line spoken after the ES click: the one heard in Spanish
const [, firstSpanishEnd] = beginnerTake.voices.find(([start]) => start >= beginner['es-speaking'] - 0.5)
const CROWD = path.resolve('../assets/audio/crowd_ambience_loop.wav')
// Zoomed in on the match (the pitch, the answer, the commentary, the Ask dock): readable in a video.
const MATCH = [250, 110, 1440, 810]

// Each segment: a clip, the window to keep (seconds into it), and the narration lines that start in it
// (line number, seconds after the segment starts).
const SEGMENTS = [
  // the three viewers and the logo, with room to breathe between the lines
  { clip: 'characters', from: 0, to: 12.0, lines: [[1, 0.4], [2, 3.1], [3, 5.8], [4, 8.3]] },
  { clip: 'logo', from: 0, to: 5.9, lines: [[5, 0.35]], into: ['circleopen', 0.6] },
  // the fan picks his club (the page turns red) and his level; the crowd comes in here
  { clip: 'live-main', from: main.club - 1.6, to: main.kickoff, lines: [[6, 0.5]], into: ['smoothleft', 0.6], crowd: true },
  // one stream: the build-up, Davis calls the goal, Roy explains it
  { crop: MATCH, clip: 'live-main', from: main.goal - 5.4, to: main['roy-done'] + 0.2, lines: [[7, 0.1]], into: ['fade', 0.5] },
  // the analyst's question (the Analyst level is on), the chart in the commentary...
  { crop: MATCH, clip: 'live-main', from: main['ask-chart'] - 3.6, to: main.chart + 3.0, lines: [[8, 0.2], [9, 3.9]], into: ['fade', 0.35] },
  // ...and Roy's answer, in full
  { crop: MATCH, clip: 'live-main', from: main['answer-speaking'] - 0.3, to: main['answer-done'] + 0.2, lines: [], into: ['fade', 0.4] },
  // Beginner, in English: the penalty, explained simply and shown on the pitch
  { crop: MATCH, clip: 'live-beginner', from: beginner.ask - 0.5, to: beginner.answer + 3.6, lines: [[10, 0.4]], into: ['smoothleft', 0.6] },
  { crop: MATCH, clip: 'live-beginner', from: beginner['answer-speaking'] - 0.3, to: beginner['answer-done'] + 0.2, lines: [], into: ['fade', 0.35] },
  // one click on ES: the whole page turns Spanish, then the commentary in Spanish
  { clip: 'live-beginner', from: beginner.es - 0.5, to: beginner.es + 6.0, lines: [[11, 0.3]], into: ['fade', 0.35] },
  { crop: MATCH, clip: 'live-beginner', from: beginner['es-speaking'] - 0.3, to: firstSpanishEnd + 0.4, lines: [], into: ['fade', 0.35] },
  // how it works, the four steps named as each card lights up (21-25), and the end card
  { clip: 'how', from: 0, to: 14.2, lines: [[21, 0.5], [22, 2.6], [23, 4.5], [24, 6.9], [25, 10.0]], into: ['smoothleft', 0.6] },
  { clip: 'end', from: 0, to: 6.3, lines: [[13, 0.5]], into: ['fade', 0.6] },
]
const TAKE_GAIN = {} // dB per take, if one needs it: each commentary line is already levelled in lib.mjs
const FADE = 0.25

// Each clip flows into the next (`into`: a crossfade within a section, a slide into a new one), so
// clips overlap by the transition's length; only the very start and end fade from and to black.
const parts = []
const placed = [] // [narration file, start in the final video]
let at = 0 // where the current segment starts in the final video
let crowdFrom = null // the crowd starts with the pre-match screen, after the intro
for (const [i, seg] of SEGMENTS.entries()) {
  const length = +(seg.to - seg.from).toFixed(2)
  const out = path.join(OUT, `part-${String(i).padStart(2, '0')}.mp4`)
  const live = seg.clip.startsWith('live-')
  const sound = live ? ['-ss', String(seg.from), '-t', String(length), '-i', path.join(OUT, `${seg.clip}-audio.wav`)]
    : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'] // the crowd comes in the final mix
  const volume = `${TAKE_GAIN[seg.clip] ?? 0}dB`
  const first = i === 0
  const last = i === SEGMENTS.length - 1
  const vfade = [first && `fade=t=in:st=0:d=${FADE}`, last && `fade=t=out:st=${length - 0.6}:d=0.6`].filter(Boolean)
  ffmpeg('-ss', String(seg.from), '-t', String(length), '-i', path.join(OUT, `${seg.clip}.mp4`), ...sound,
    '-filter_complex',
    `[0:v]${seg.crop ? `crop=${seg.crop[2]}:${seg.crop[3]}:${seg.crop[0]}:${seg.crop[1]},scale=1920:1080:flags=lanczos,` : ''}` +
    `${vfade.length ? vfade.join(',') + ',' : ''}fps=30,format=yuv420p[v];` +
    `[1:a]atrim=0:${length},asetpts=PTS-STARTPTS,volume=${volume}${last ? `,afade=t=out:st=${length - 0.6}:d=0.6` : ''}[a]`,
    '-map', '[v]', '-map', '[a]', '-t', String(length), '-r', '30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17',
    '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k', out)
  if (i > 0) at -= seg.into[1] // starts as the previous clip is still finishing
  parts.push({ file: out, length, start: at, into: seg.into })
  if (seg.crowd && crowdFrom === null) crowdFrom = at
  for (const [line, offset] of seg.lines) {
    const file = ['m4a', 'mp3', 'wav', 'aiff', 'caf'].map((ext) => path.join(NARRATION, `${String(line).padStart(2, '0')}.${ext}`))
      .find((f) => fs.existsSync(f))
    if (file) placed.push([file, at + offset])
    else console.log(`  (no narration line ${line} yet)`)
  }
  at += length
}
const joined = path.join(OUT, 'joined.mp4')
const filters = []
let v = '[0:v]'
let a = '[0:a]'
parts.slice(1).forEach((part, k) => {
  const i = k + 1
  const [type, duration] = part.into
  filters.push(`${v}[${i}:v]xfade=transition=${type}:duration=${duration}:offset=${part.start.toFixed(3)}[v${i}]`)
  filters.push(`${a}[${i}:a]acrossfade=d=${duration}[a${i}]`)
  v = `[v${i}]`
  a = `[a${i}]`
})
ffmpeg(...parts.flatMap((p) => ['-i', p.file]), '-filter_complex', filters.join(';'), '-map', v, '-map', a,
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', '-c:a', 'aac', '-b:a', '192k', joined)

// The final mix: one steady crowd under everything, the commentary (turned right down whenever the
// narrator speaks, back up between lines) and the narration on top.
const final = path.resolve(placed.length ? 'your-call-demo.mp4' : 'your-call-demo-draft.mp4')
const inputs = ['-i', joined, '-stream_loop', '-1', '-i', CROWD]
const voice = []
placed.forEach(([file, start], i) => {
  inputs.push('-i', file)
  const ms = Math.round(start * 1000)
  voice.push(`[${i + 2}:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,loudnorm=I=-16:TP=-1.5,adelay=${ms}|${ms}[n${i}]`)
})
const crowdMs = Math.round((crowdFrom ?? 0) * 1000)
const crowd = `[1:a]aresample=48000,atrim=0:${(at - (crowdFrom ?? 0)).toFixed(2)},volume=0.17,afade=t=in:d=1.5,` +
  `afade=t=out:st=${(at - (crowdFrom ?? 0) - 1.2).toFixed(2)}:d=1.2,adelay=${crowdMs}|${crowdMs},apad[crowd]`
const filter = placed.length
  ? `${voice.join(';')};${placed.map((_, i) => `[n${i}]`).join('')}amix=inputs=${placed.length}:normalize=0,apad,asplit=2[narr][key];` +
    '[0:a][key]sidechaincompress=threshold=0.008:ratio=20:attack=15:release=350:makeup=1[talk];' +
    `${crowd};[talk][crowd][narr]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.95[out]`
  : `${crowd};[0:a][crowd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[out]`
ffmpeg(...inputs, '-filter_complex', filter, '-map', '0:v', '-map', '[out]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', final)
console.log(`${path.basename(final)}: ${at.toFixed(1)} s, ${placed.length} narration lines`)
