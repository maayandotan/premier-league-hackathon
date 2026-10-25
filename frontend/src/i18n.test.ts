import { describe, expect, it } from 'vitest'
import { translator } from './i18n'

describe('the page in Spanish', () => {
  const es = translator('es')

  it('translates text and fills in values', () => {
    expect(es('Kick off')).toBe('Comenzar')
    expect(es('Matchday {n}', { n: 11 })).toBe('Jornada 11')
    expect(es('Something new')).toBe('Something new') // a missing entry shows the English, never a blank
  })

  it('translates the backend words for why a moment mattered', () => {
    expect(es.reason('late go-ahead goal, against the run of play'))
      .toBe('gol para ponerse arriba al final, contra la corriente del juego')
    expect(es.reason('big chance, saved')).toBe('ocasión clara, atajado')
    expect(es.reason('penalty equalizer')).toBe('penal: empate')
  })

  it('rewrites the live pattern lines and keeps their numbers', () => {
    expect(es.pattern('6 of 7 final-third entries down the right in the last 15 minutes'))
      .toBe('6 de 7 llegadas al último tercio por la derecha en los últimos 15 minutos')
    expect(es.pattern('a line we have not seen')).toBe('a line we have not seen')
  })

  it('leaves English alone', () => {
    const en = translator('en')
    expect(en('Kick off')).toBe('Kick off')
    expect(en.reason('big chance, saved')).toBe('big chance, saved')
    expect(en.form('W')).toBe('W')
    expect(es.form('W')).toBe('G')
  })
})
