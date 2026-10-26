import { createContext, useContext } from 'react'

/** The page in the viewer's language. Text is keyed by its English wording, so the components read
 * as before: t('Kick off'). A missing Spanish entry shows the English, never a blank. */
export type Lang = 'en' | 'es'

const ES: Record<string, string> = {
  // header and controls
  'The match, explained your way': 'El partido, explicado a tu manera',
  'Kick off': 'Comenzar', Restart: 'Reiniciar', Mute: 'Silenciar', Unmute: 'Activar sonido',
  'Sound off': 'Sonido apagado', 'Sound on': 'Sonido encendido', 'Supporting {club}': 'Hincha de {club}',
  Beginner: 'Principiante', Fan: 'Aficionado', Analyst: 'Analista',
  'New to football': 'Nuevo en el fútbol', 'Knows the game': 'Conoce el juego', 'Wants the details': 'Quiere los detalles',
  'Commentary level': 'Nivel de los comentarios', Language: 'Idioma',
  // pre-match
  'Matchday {n}: pick a match': 'Jornada {n}: elige un partido', 'Matchday {n}': 'Jornada {n}',
  'Kick-off': 'Previa', vs: 'vs', 'Starting line-ups': 'Alineaciones',
  'Your commentators:': 'Tus comentaristas:', 'calls the action,': 'narra la acción,',
  'explains why it matters.': 'explica por qué importa.',
  'Ask them anything while the match goes on.': 'Pregúntales lo que quieras mientras sigue el partido.',
  'Your club': 'Tu club', '(optional)': '(opcional)', 'Neutral: no club picked': 'Neutral: sin club elegido',
  'How well do you know football?': '¿Cuánto sabes de fútbol?',
  BEGINNER: 'PRINCIPIANTE', FAN: 'AFICIONADO', ANALYST: 'ANALISTA',
  'I follow the game': 'Sigo el fútbol', 'Give me the numbers': 'Dame los números',
  'Everything explained, no jargon': 'Todo explicado, sin jerga',
  'Clear football talk, a few numbers': 'Fútbol claro, algunos números',
  'xG, possession and the tactics': 'xG, posesión y táctica',
  'Turn your sound on': 'Activa el sonido', Match: 'Partido', 'Before kick-off': 'Antes del partido',
  'Live · AI broadcast': 'En vivo · transmisión con IA',
  'Two AI commentators.': 'Dos comentaristas con IA.', 'Your level.': 'A tu nivel.',
  'A caller for the action, an analyst for the why, and a crowd that roars on every goal. Ask them anything, by voice, while the match goes on.': 'Un narrador para la acción, un analista para el porqué y un público que ruge en cada gol. Pregúntales lo que quieras, por voz, mientras sigue el partido.',
  // scorebug and timeline
  '1st half': '1er tiempo', '2nd half': '2do tiempo', 'Extra time': 'Tiempo extra', Penalties: 'Penales',
  'Full time': 'Final', 'Pre-match': 'Previa', FT: 'FIN', Goal: 'Gol', Card: 'Tarjeta',
  Momentum: 'Dominio', 'Evenly matched': 'Parejo', '{team} on top': '{team} domina',
  // commentary feed
  Commentary: 'Comentarios', Questions: 'Preguntas', Question: 'Pregunta', 'On air': 'Al aire', 'On Air': 'Al aire',
  'Play-by-play': 'Narrador', 'Answering you': 'Te responde', You: 'Tú', 'asked at {clock}': 'preguntó al {clock}',
  'Thinking...': 'Pensando...', 'Roy is analyzing match data...': 'Ricardo está analizando los datos...',
  'No questions asked yet. Ask Roy below!': 'Aún no hay preguntas. ¡Pregúntale a Ricardo abajo!',
  'The commentators are ready. Kick off to hear them.': 'Los comentaristas están listos. Comienza para escucharlos.',
  AI: 'IA', Auto: 'Auto', 'Speaking now': 'Hablando ahora',
  beginner: 'principiante', fan: 'aficionado', analyst: 'analista',
  // question box
  'What did I miss?': '¿Qué me perdí?', 'Why was that a foul?': '¿Por qué fue falta?',
  'Who has been better?': '¿Quién ha jugado mejor?', 'Who has been better so far?': '¿Quién ha sido mejor hasta ahora?',
  'What is offside?': '¿Qué es el fuera de lugar?', 'What was the key tactical change?': '¿Cuál fue el cambio táctico clave?', 'Who was the better team?': '¿Quién fue mejor equipo?',
  'What was the key moment?': '¿Cuál fue el momento clave?', 'Was the result deserved?': '¿Fue justo el resultado?',
  "Didn't catch that. Try again?": 'No te entendí. ¿Lo intentas otra vez?',
  'Microphone blocked. Allow it in the browser to ask by voice.': 'Micrófono bloqueado. Permítelo en el navegador para preguntar por voz.',
  'The microphone did not work.': 'El micrófono no funcionó.',
  'Ask the analyst': 'Pregúntale al analista', 'Stop and send': 'Detener y enviar', 'Ask by voice': 'Preguntar por voz',
  'Listening… press the mic again to send': 'Escuchando… pulsa el micrófono otra vez para enviar',
  'Full time: ask Roy about the match…': 'Final: pregúntale a Ricardo sobre el partido…',
  'Ask Roy about the match…': 'Pregúntale a Ricardo sobre el partido…', 'Kick off to ask questions': 'Comienza para hacer preguntas',
  'Your question': 'Tu pregunta', Ask: 'Preguntar',
  '{team}: results by goals scored': '{team}: resultados según los goles marcados',
  '{n} league matches this season': '{n} partidos de liga esta temporada', 'Scored {n}': 'Marcó {n}',
  'The match, while you scroll': 'El partido, mientras bajas', 'big chance': 'ocasión clara', 'half chance': 'media ocasión', 'hard chance': 'ocasión difícil',
  won: 'ganados', drawn: 'empatados', lost: 'perdidos', 'no matches': 'sin partidos',
  '{player}: shots and goals by match time': '{player}: tiros y goles según el minuto',
  '{shots} shots, {goals} goals this season': '{shots} tiros, {goals} goles esta temporada',
  'Shots and goals by match time': 'Tiros y goles según el minuto', Goals: 'Goles', Penalty: 'Penal',
  scored: 'marcado', missed: 'fallado', 'Expected goals adding up': 'Goles esperados acumulados',
  "This match, to {m}'": "Este partido, hasta el {m}'", 'Ask {name}': 'Pregúntale a {name}', Close: 'Cerrar',
  'By voice or text. The match keeps playing while he answers.': 'Por voz o texto. El partido sigue mientras responde.',
  '{name} is looking at the data… the match goes on': '{name} está mirando los datos… el partido sigue',
  'Ask {name} anything, any time': 'Pregúntale a {name} lo que quieras, cuando quieras',
  '“Why was that a foul?” “Who has been better?” Ask by voice or text: the match keeps playing while he answers, at your level.':
    '“¿Por qué fue falta?” “¿Quién ha jugado mejor?” Pregunta por voz o texto: el partido sigue mientras responde, a tu nivel.',
  "Listening… press the mic again when you're done": 'Escuchando… pulsa el micrófono otra vez al terminar',
  'Roy is thinking… the match goes on': 'Ricardo está pensando… el partido sigue',
  // questions table
  "Your questions and Roy's real-time personalized analysis": 'Tus preguntas y el análisis personalizado de Ricardo en vivo',
  'Search questions...': 'Buscar preguntas...', 'Search questions': 'Buscar preguntas', 'Clear search': 'Borrar búsqueda',
  'No questions asked yet': 'Aún no hay preguntas',
  'Ask Roy about fouls, tactics, key moments, or rules using the question box or microphone.': 'Pregúntale a Ricardo sobre faltas, táctica, momentos clave o reglas con la caja de preguntas o el micrófono.',
  'His answers will appear here in real time!': '¡Sus respuestas aparecerán aquí en vivo!',
  'Try asking:': 'Prueba a preguntar:', 'No questions match "{q}".': 'Ninguna pregunta coincide con "{q}".',
  Time: 'Minuto', 'Question (You)': 'Pregunta (tú)', "Roy's Analysis": 'Análisis de Ricardo', 'Roy (Analyst)': 'Ricardo (analista)',
  'Asked at {clock}': 'Preguntado al {clock}', 'Questions Table': 'Tabla de preguntas',
  // lower cards
  'Your club this season': 'Tu club esta temporada', '{n} in the league': '{n}º en la liga',
  '{points} pts from {played}': '{points} pts en {played}', '{w}W {d}D {l}L': '{w}G {d}E {l}P',
  'Form, last five': 'Forma, últimos cinco', Today: 'Hoy', Captain: 'Capitán', v: 'vs', at: 'en casa de',
  'Top scorers': 'Goleadores', 'Top assists': 'Asistencias', 'No goals yet': 'Aún sin goles', 'No assists yet': 'Aún sin asistencias',
  'Match stats': 'Estadísticas', 'The match in numbers': 'El partido en números',
  'Who has had the ball': 'Quién ha tenido el balón', 'Shots at goal': 'Tiros a puerta',
  'The team with more of the ball usually controls the game.': 'El equipo con más balón suele controlar el partido.',
  'Every attempt to score, whether it went in, was saved or missed.': 'Cada intento de gol: dentro, atajado o fuera.',
  Possession: 'Posesión', 'Last 10 min': 'Últimos 10 min', Shots: 'Tiros', 'Expected goals': 'Goles esperados',
  'Progressive passes': 'Pases progresivos',
  'Tempo: {label} ({n} possession changes a minute) · Momentum {m} (home +1, away −1)': 'Ritmo: {label} ({n} cambios de posesión por minuto) · Dominio {m} (local +1, visitante −1)',
  chaotic: 'caótico', controlled: 'controlado', balanced: 'equilibrado',
  'adding up over the match': 'acumulados en el partido', 'The chart fills in as the match goes on.': 'El gráfico se llena a medida que avanza el partido.',
  'Tactical patterns': 'Patrones tácticos', 'last 15 minutes': 'últimos 15 minutos', 'no data yet': 'aún sin datos',
  'Final-third entries this match: {n}': 'Llegadas al último tercio en el partido: {n}',
  "Final-third entries this match by side, from each team's own attacking view.": 'Llegadas al último tercio por banda, vistas desde el ataque de cada equipo.',
  left: 'izquierda', centre: 'centro', right: 'derecha',
  'Football basics': 'Lo básico del fútbol',
  'Ask Roy about anything else, any time: the match keeps going.': 'Pregúntale a Ricardo lo que sea, cuando quieras: el partido sigue.',
  'Key moments': 'Momentos clave', 'Goals, cards and big chances will appear here.': 'Aquí aparecerán goles, tarjetas y ocasiones claras.',
  'League table': 'Tabla', Club: 'Club', P: 'PJ', GD: 'DG', Pts: 'Pts', Form: 'Forma',
  'Fictional teams and players · Crowd audio: “Free Crowd Cheering Sounds” by Gregor Quendel, CC BY 4.0': 'Equipos y jugadores ficticios · Audio del público: “Free Crowd Cheering Sounds” de Gregor Quendel, CC BY 4.0',
  'Lost the connection to the match. Press Kick off to watch again.': 'Se perdió la conexión con el partido. Pulsa Comenzar para verlo de nuevo.',
}

// The football basics for beginners, in Spanish (our own words, like the English ones).
export const BASICS_ES: [string, string][] = [
  ['Gol', 'El balón entra entero entre los postes. Gana el equipo con más goles al final.'],
  ['Tiro libre', 'Tras una falta, el equipo que la recibió saca desde ese punto. Cerca del arco, puede tirar.'],
  ['Penal', 'Falta de un defensor en su propia área: un tiro desde 11 metros, solo contra el portero.'],
  ['Fuera de lugar', 'Un atacante no puede esperar detrás del último defensor un pase. En la misma línea vale.'],
  ['Tarjetas', 'La amarilla es una advertencia. Dos amarillas, o una roja, y el jugador sale: su equipo juega con 10.'],
  ['Tiro de esquina', 'Si un defensor saca el balón por su propia línea de fondo, los atacantes sacan desde la esquina.'],
]

// Why a moment mattered (the ranker's words), piece by piece: "late go-ahead goal, against the run of play".
const REASONS: Record<string, string> = {
  equalizer: 'empate', 'go-ahead goal': 'gol para ponerse arriba', 'extends the lead': 'amplía la ventaja',
  'pulls one back': 'descuenta', 'against the run of play': 'contra la corriente del juego',
  'hits the post': 'al palo', 'big chance': 'ocasión clara', 'half chance': 'media ocasión',
  'speculative effort': 'tiro lejano', 'sent off': 'expulsado', booked: 'amonestado', 'penalty awarded': 'penal',
  'free kick in shooting range': 'tiro libre peligroso', foul: 'falta', offside: 'fuera de lugar', 'kick-off': 'saque inicial',
  'half-time': 'medio tiempo', 'full time': 'final del partido', 'sets up a shot': 'prepara un tiro', corner: 'tiro de esquina',
  'ball into the box': 'balón al área', 'rare line-breaking pass': 'pase que rompe líneas', 'carries into the box': 'entra al área',
  'beats a defender in the final third': 'se va de un defensor', saved: 'atajado', 'off target': 'fuera', blocked: 'bloqueado',
  goal: 'gol', scored: 'gol', 'saved onto the post': 'atajado al palo', post: 'palo', wayward: 'desviado', substitution: 'cambio', 'injury stoppage': 'pausa por lesión',
}

function reasonEs(reason: string): string {
  return reason.split(', ').map((part) => {
    if (part.startsWith('shootout penalty ')) return `penal en la tanda: ${REASONS[part.slice(17)] ?? part.slice(17)}`
    let words = part
    let late = false
    let penalty = false
    if (words.startsWith('late ')) { late = true; words = words.slice(5) }
    if (words.startsWith('penalty ') && words !== 'penalty awarded') { penalty = true; words = words.slice(8) }
    const base = REASONS[words] ?? words
    return `${penalty ? 'penal: ' : ''}${base}${late ? ' al final' : ''}`
  }).join(', ')
}

// The live pattern lines (patterns.py), rewritten into Spanish. Numbers and team names stay as they are.
const SIDES: Record<string, string> = { left: 'la izquierda', centre: 'el centro', right: 'la derecha' }
const PATTERNS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^(\d+) of (\d+) final-third entries down the (\w+) in the last 15 minutes$/,
    (m) => `${m[1]} de ${m[2]} llegadas al último tercio por ${SIDES[m[3]] ?? m[3]} en los últimos 15 minutos`],
  [/^(\d+) quick attacks straight after winning the ball in the last 15 minutes$/,
    (m) => `${m[1]} ataques rápidos justo después de recuperar el balón en los últimos 15 minutos`],
  [/^won the ball (\d+) times in the opponent's half in the last 15 minutes \((\d+) for (.+)\)$/,
    (m) => `recuperó el balón ${m[1]} veces en campo rival en los últimos 15 minutos (${m[2]} para ${m[3]})`],
  [/^(\d+) crosses in the last 15 minutes, (\d+) led to a shot$/,
    (m) => `${m[1]} centros en los últimos 15 minutos, ${m[2]} terminaron en tiro`],
  [/^(\d+)% of all the passes played in the final third, territory not a side, in the last 15 minutes$/,
    (m) => `${m[1]}% de todos los pases jugados en el último tercio, en los últimos 15 minutos`],
  [/^no clear pattern in the last 15 minutes$/, () => 'sin un patrón claro en los últimos 15 minutos'],
]

function patternEs(line: string): string {
  for (const [pattern, write] of PATTERNS) {
    const m = line.match(pattern)
    if (m) return write(m)
  }
  return line
}

export type T = ((text: string, vars?: Record<string, string | number>) => string) & {
  lang: Lang
  reason: (reason: string) => string
  pattern: (line: string) => string
  form: (result: string) => string // W/D/L -> G/E/P
  voice: (commentator: string) => string // Davis and Roy are Juan and Ricardo in Spanish
}

const NAMES_ES: Record<string, string> = { Davis: 'Juan', Roy: 'Ricardo' }

const FORM_ES: Record<string, string> = { W: 'G', D: 'E', L: 'P' }

export function translator(lang: Lang): T {
  const t = ((text: string, vars?: Record<string, string | number>) => {
    let out = lang === 'es' ? ES[text] ?? text : text
    for (const [key, value] of Object.entries(vars ?? {})) out = out.replaceAll(`{${key}}`, String(value))
    return out
  }) as T
  t.lang = lang
  t.reason = (reason) => (lang === 'es' ? reasonEs(reason) : reason)
  t.pattern = (line) => (lang === 'es' ? patternEs(line) : line)
  t.voice = (commentator) => (lang === 'es' ? NAMES_ES[commentator] ?? commentator : commentator)
  t.form = (result) => (lang === 'es' ? FORM_ES[result] ?? result : result)
  return t
}

export const LangContext = createContext<T>(translator('en'))

export const useT = () => useContext(LangContext)
