/** A TV-style 3-letter code: "Westvale United" -> "WEU", "Argentina" -> "ARG". */
export function teamCode(name: string): string {
  const words = name.split(/\s+/).filter((w) => !/^(fc|cf|afc|sc)$/i.test(w))
  const code = words.length === 1 ? words[0].slice(0, 3) : words[0].slice(0, 2) + words[1][0]
  return code.toUpperCase()
}
