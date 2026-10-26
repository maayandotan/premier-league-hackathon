/** The Meridian League's crests: our own designs. Each club has a badge shape, its second colour and an
 * emblem from its name (Northbridge a bridge, Highcastle a tower, Saltmarsh an anchor...). Emblems are
 * drawn in a 16 x 16 box: `fill` paths are solid, `stroke` paths are lines. */
export type CrestShape = 'shield' | 'round' | 'badge'

export interface CrestDesign {
  shape: CrestShape
  secondary: string // the club's second colour: the rim and the emblem
  fill?: string
  stroke?: string
}

export const CRESTS: Record<string, CrestDesign> = {
  NOR: { shape: 'shield', secondary: '#f8fafc', stroke: 'M1 12.5h14M2.5 12.5C5 5 11 5 13.5 12.5M5.2 12.5V8.6M8 12.5V7M10.8 12.5V8.6' },
  WEU: { shape: 'round', secondary: '#f8fafc', fill: 'M0 14L5 6l3 4 3-6 5 10z' },
  CAL: { shape: 'badge', secondary: '#e0f2fe',
    stroke: 'M1 5c2-2 4 2 7 0s5 2 7 0M1 9c2-2 4 2 7 0s5 2 7 0M1 13c2-2 4 2 7 0s5 2 7 0' },
  RED: { shape: 'shield', secondary: '#111827',
    stroke: 'M4 15V6M8 15V2.5M12 15V6M4 6c-1-1.5-.5-3 .8-3.8M8 2.5c1.2-.8 2.4-1 3.2-.4M12 6c.4-1.6 1.6-2.4 3-2.4' },
  OAK: { shape: 'round', secondary: '#f8fafc', fill: 'M2.5 7.5a5.5 3 0 0 1 11 0zM4 8.5h8c0 4.5-1.8 7-4 7s-4-2.5-4-7z',
    stroke: 'M8 1.5v3' },
  ELM: { shape: 'round', secondary: '#1e3a8a', fill: 'M8 .8a6 6 0 1 1 0 12 6 6 0 1 1 0-12zM7 12h2v4H7z' },
  BRA: { shape: 'badge', secondary: '#f8fafc',
    stroke: 'M8 15.5V1.5M8 4L4.5 2.8M8 4l3.5-1.2M8 7.2L3.5 5.8M8 7.2l4.5-1.4M8 10.4L3 9M8 10.4l5-1.4M8 13.4L4 12.2M8 13.4l4-1.2' },
  SIL: { shape: 'shield', secondary: '#0f172a',
    fill: 'M0 7c3-2 5 2 8 0s5 2 8 0v3.2c-3 2-5-2-8 0s-5-2-8 0z', stroke: 'M8 1.5l1 2 2.2.3-1.6 1.5.4 2.2L8 6.4 6 7.5l.4-2.2-1.6-1.5L7 3.5z' },
  RAV: { shape: 'badge', secondary: '#f59e0b',
    fill: 'M1 9.5c3-.5 5-3.5 7.2-3.5L10 4l2 .8 3 .2-2.2 1.6c0 3-2 5.2-5 6l-2.2 2-.8-2.2C3 12.2 1.8 11.2 1 9.5z' },
  HIG: { shape: 'shield', secondary: '#facc15', fill: 'M3 15.5V4h2.2v2.2h1.7V4h2.2v2.2h1.7V4H13v11.5H9.5V12a1.5 1.5 0 0 0-3 0v3.5z' },
  LAR: { shape: 'round', secondary: '#fde047', stroke: 'M1 8.5c2.6-3.2 5-3.2 7 .2 2-3.4 4.4-3.4 7-.2M5 12.5c1.4-1.6 2.6-1.6 3 0 .4-1.6 1.6-1.6 3 0' },
  FEN: { shape: 'badge', secondary: '#facc15', fill: 'M8 .8L13 7.5h-2.8l3.8 5H2l3.8-5H3zM7 12.5h2V16H7z' },
  IRO: { shape: 'shield', secondary: '#f97316',
    fill: 'M1.5 4.5H13c0 1.6 1.4 2.2 2.5 2.2v1.2c-1.8 0-3 .9-3.8 2.1v1.8h1.8v2.2H3.5V11.8h1.8V10C3.6 8.6 2.4 6.8 1.5 4.5z' },
  GLE: { shape: 'round', secondary: '#f8fafc', fill: 'M0 10.5L5 3l3 4.2L10.2 5 16 10.5z', stroke: 'M2 13h12M4.5 15.4h7' },
  ASH: { shape: 'shield', secondary: '#1c1917',
    fill: 'M8 .8c1 3 5 5 5 9.2a5 5 0 0 1-10 0c0-2 .9-3.2 2-4.2 0 2 .9 3.1 2 3.1 0-3-1.2-5 1-8.1z' },
  SAL: { shape: 'round', secondary: '#f8fafc',
    stroke: 'M8 4.2v11M5 7h6M2 10.5c0 2.8 2.8 4.8 6 4.8s6-2 6-4.8M8 1a1.6 1.6 0 1 1 0 3.2A1.6 1.6 0 1 1 8 1z' },
  HOL: { shape: 'badge', secondary: '#f8fafc', fill: 'M10.5 1a7 7 0 1 0 5 12.4A6 6 0 0 1 10.5 1z' },
  WHI: { shape: 'round', secondary: '#1e40af', fill: 'M0 2.5h8.2l1.2 2.2V9l2.2 3.2H0z',
    stroke: 'M10 14.6c1-1 2 1 3 0s2 1 3 0' },
  BRI: { shape: 'shield', secondary: '#f8fafc', fill: 'M1 12L2 3.8l4 4L8 1.5l2 6.3 4-4L15 12zM1 13.2h14v2.2H1z' },
  COP: { shape: 'badge', secondary: '#fcd34d',
    stroke: 'M8 15.5V2.5M8 5c-2 0-3-1.6-3-3 2 0 3 1.2 3 3zM8 5c2 0 3-1.6 3-3-2 0-3 1.2-3 3zM8 9.2c-2 0-3-1.6-3-3 2 0 3 1.2 3 3zM8 9.2c2 0 3-1.6 3-3-2 0-3 1.2-3 3zM8 13.2c-2 0-3-1.6-3-3 2 0 3 1.2 3 3zM8 13.2c2 0 3-1.6 3-3-2 0-3 1.2-3 3z' },
}

/** Each shape's outline (the rim) and its inner field, in the crest's 40 x 46 box. */
export const SHAPES: Record<CrestShape, { outer: string; inner: string }> = {
  shield: {
    outer: 'M20 2 L37 8 V22 C37 33 29 40 20 44 C11 40 3 33 3 22 V8 Z',
    inner: 'M20 5.5 L33.8 10.4 V22 C33.8 31 27.5 36.6 20 40.3 C12.5 36.6 6.2 31 6.2 22 V10.4 Z',
  },
  round: {
    outer: 'M20 4 a19 19 0 1 1 0 38 a19 19 0 1 1 0 -38 Z',
    inner: 'M20 7.2 a15.8 15.8 0 1 1 0 31.6 a15.8 15.8 0 1 1 0 -31.6 Z',
  },
  badge: {
    outer: 'M7 2 H33 Q38 2 38 7 V24 C38 34 29 41 20 44 C11 41 2 34 2 24 V7 Q2 2 7 2 Z',
    inner: 'M8 5.2 H32 Q34.8 5.2 34.8 8 V24 C34.8 32.4 27.4 38.2 20 40.8 C12.6 38.2 5.2 32.4 5.2 24 V8 Q5.2 5.2 8 5.2 Z',
  },
}
