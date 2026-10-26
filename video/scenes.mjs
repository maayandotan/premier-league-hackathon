// Records our own scenes (the three viewers, the logo, how it works, the end card) to video clips.
import fs from 'node:fs/promises'
import path from 'node:path'
import { H, launch, OUT, recordVideo, W } from './lib.mjs'

const SCENES = [
  ['characters', 12.3],
  ['logo', 5],
  ['how', 14.6],
  ['end', 6],
]

await fs.mkdir(OUT, { recursive: true })
const browser = await launch()
for (const [name, seconds] of SCENES.filter(([n]) => !process.argv[2] || process.argv.includes(n))) {
  const page = await browser.newPage({ viewport: { width: W, height: H } })
  const url = `file://${path.resolve('scenes', `${name}.html`)}`
  // Wait for the fonts before starting: the animations begin when the page loads, so load it inside
  // the recording, from a blank dark page.
  await page.setContent('<body style="margin:0;background:#07101f"></body>')
  const video = await recordVideo(page, name, async () => {
    await page.goto(url, { waitUntil: 'networkidle' })
    await page.waitForTimeout(seconds * 1000)
  })
  console.log(name, `${(video.end - video.start).toFixed(1)} s, ${video.frames} frames`)
  await page.close()
}
await browser.close()
