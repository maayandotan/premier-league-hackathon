// Records the live site the way a viewer uses it, with its sound, and notes when each moment happens
// (the edit cuts around those marks). Two takes: the fan/analyst one in English, the beginner in Spanish.
import fs from 'node:fs/promises'
import path from 'node:path'
import { buildSoundtrack, H, launch, listenToAudio, OUT, recordVideo, W } from './lib.mjs'

const SITE = process.env.SITE ?? 'https://your-call.purplesand-eefdeaf2.francecentral.azurecontainerapps.io'
const ASSETS = { crowd: path.resolve('../assets/audio/crowd_ambience_loop.wav'),
                 roar: path.resolve('../assets/audio/crowd_goal_roar.wav') }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function smoothScroll(page, selector, block = 'center') {
  await page.evaluate(([sel, b]) => document.querySelector(sel)?.scrollIntoView({ behavior: 'smooth', block: b }),
    [selector, block])
  await sleep(1100)
}

async function ask(page, question) {
  const input = page.locator('.ask.dock input')
  await input.scrollIntoViewIfNeeded()
  await input.click()
  await page.keyboard.type(question, { delay: 55 })
  await sleep(400)
  await page.keyboard.press('Enter')
}

// Roy's answer is on the pitch and data-speaking while its audio plays: wait for it to start, then end.
async function waitForAnswerSpoken(page, mark, label) {
  await page.waitForSelector('.answer-card .answer-a[data-speaking="true"]', { timeout: 45000 })
  mark(`${label}-speaking`)
  await page.waitForSelector('.answer-card .answer-a[data-speaking="true"]', { state: 'detached', timeout: 60000 })
  mark(`${label}-done`)
}

const TAKES = {
  // The fan picks his club (the whole page turns red) and the Fan level; the goal and Roy's
  // explanation; then the switch to Analyst and a question answered with a chart, spoken in full.
  async main(page, mark) {
    await page.goto(`${SITE}/?start=62&speed=3`, { waitUntil: 'networkidle' })
    await sleep(2000)
    mark('prematch')
    await smoothScroll(page, '.pm-club')
    await sleep(500)
    await page.locator('.pm-club-list button[aria-label="Westvale United"]').click()
    mark('club')
    await sleep(900)
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    await sleep(2600)
    mark('red')
    await smoothScroll(page, '.pm-level')
    await page.locator('.pm-choices label[data-level="fan"]').click()
    mark('level')
    await sleep(1300)
    await smoothScroll(page, '.pm-go')
    await page.locator('.prematch .kickoff').click()
    mark('kickoff')
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    await page.waitForSelector('.goal-banner', { timeout: 90000 })
    mark('goal')
    await page.waitForSelector('.lower-third.analyst', { timeout: 40000 })
    mark('roy')
    await page.waitForSelector('.lower-third.analyst', { state: 'detached', timeout: 40000 })
    mark('roy-done')
    await page.locator('.topbar .level-picker:not(.lang-picker) button[aria-label="Analyst"]').click()
    mark('analyst')
    await sleep(900)
    await ask(page, 'Show me how the chances have built up in this match')
    mark('ask-chart')
    await page.waitForSelector('.feed .line .answer-chart', { timeout: 30000 })
    mark('chart')
    await waitForAnswerSpoken(page, mark, 'answer')
    await sleep(900)
    mark('end')
  },

  // Beginner, in English first: the penalty explained simply and shown on the pitch. Then the ES
  // button: the page turns Spanish and Ricardo answers a question in Spanish.
  async beginner(page, mark) {
    await page.goto(`${SITE}/?start=72&speed=3&level=fan&team=Westvale%20United`, { waitUntil: 'networkidle' })
    await sleep(1200)
    await smoothScroll(page, '.pm-go')
    await page.locator('.prematch .kickoff').click()
    mark('kickoff')
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    await sleep(2500)
    await page.locator('.topbar .level-picker:not(.lang-picker) button[aria-label="Beginner"]').click()
    mark('beginner')
    await page.waitForFunction(() => [...document.querySelectorAll('.feed li.line p')]
      .some((p) => /penalty/i.test(p.textContent ?? '')), null, { timeout: 120000 })
    mark('penalty')
    await sleep(2500)
    await ask(page, 'Why was that a penalty?')
    mark('ask')
    await page.waitForSelector('.answer-card.answered', { timeout: 40000 })
    mark('answer')
    await waitForAnswerSpoken(page, mark, 'answer')
    await sleep(600)
    await page.locator('.topbar .lang-picker button', { hasText: 'ES' }).click()
    mark('es')
    // the first commentary line spoken in Spanish, heard in full
    const spanish = () => [...document.querySelectorAll('.feed li.line[data-speaking="true"] p')]
      .some((p) => /[¡¿ñáéíóú]|\b(el|la|del|para|con|por)\b/i.test(p.textContent ?? ''))
    await page.waitForFunction(spanish, null, { timeout: 60000, polling: 100 })
    mark('es-speaking')
    await page.waitForFunction(() => !document.querySelector('.feed li.line[data-speaking="true"]'), null,
      { timeout: 60000, polling: 100 })
    mark('es-done')
    await sleep(900)
    mark('end')
  },
}

await fs.mkdir(OUT, { recursive: true })
const browser = await launch()
for (const name of Object.keys(TAKES).filter((n) => !process.argv[2] || process.argv.includes(n))) {
  const context = await browser.newContext({ viewport: { width: W, height: H } })
  const page = await context.newPage()
  const audio = await listenToAudio(page)
  const marks = {}
  const mark = (label) => { marks[label] = Date.now() / 1000; console.log(`  ${name}: ${label}`) }
  await page.setContent('<body style="margin:0;background:#07101f"></body>')
  const video = await recordVideo(page, `live-${name}`, () => TAKES[name](page, mark))
  await buildSoundtrack(`live-${name}`, video, audio, ASSETS)
  const relative = Object.fromEntries(Object.entries(marks).map(([k, v]) => [k, +(v - video.start).toFixed(2)]))
  // when Davis and Roy speak: the edit puts the narration in the gaps between them
  const voices = audio.played.filter((p) => p.kind === 'voice')
    .map((p) => [+(p.at - video.start).toFixed(2), +(p.at - video.start + p.seconds).toFixed(2)])
  const played = audio.played.map((p) => ({ ...p, at: +(p.at - video.start).toFixed(3) }))
  await fs.writeFile(path.join(OUT, `live-${name}.json`), JSON.stringify({ marks: relative, voices, played,
    length: +(video.end - video.start).toFixed(2), sounds: audio.played.length }, null, 1))
  console.log(name, relative, `${audio.played.length} sounds`)
  await context.close()
}
await browser.close()
