// Rebuilds a take's soundtrack from what live.mjs saved (when each sound played, and the clips),
// without recording it again:   node rebuild.mjs main beginner
import fs from 'node:fs'
import path from 'node:path'
import { buildSoundtrack, OUT } from './lib.mjs'

const ASSETS = { crowd: path.resolve('../assets/audio/crowd_ambience_loop.wav'),
                 roar: path.resolve('../assets/audio/crowd_goal_roar.wav') }
for (const take of process.argv.slice(2)) {
  const { played, length } = JSON.parse(fs.readFileSync(path.join(OUT, `live-${take}.json`)))
  const clips = new Map(played.filter((p) => p.kind === 'voice')
    .map((p) => [p.id, fs.readFileSync(path.join(OUT, `live-${take}-${p.id}.mp3`))]))
  await buildSoundtrack(`live-${take}`, { start: 0, end: length }, { played, clips }, ASSETS)
  console.log(take, 'rebuilt')
}
