/**
 * The viewer's microphone (#21): streams their voice to Azure Speech and returns the text.
 * Words appear while they speak (onPartial). Listening ends when they finish the sentence, when
 * they press the mic again (stop), or after a safety limit. It can never get stuck: noise around a
 * goal kept recognition open with the old version, and the viewer couldn't ask anything.
 * The browser never sees our key: it gets a 10-minute token from /api/speech-token.
 */
import {
  AudioConfig,
  ResultReason,
  SpeechConfig,
  SpeechRecognizer,
} from 'microsoft-cognitiveservices-speech-sdk'

const MAX_LISTEN_MS = 15_000

interface Token {
  token: string
  region: string
}

async function fetchToken(): Promise<Token> {
  const response = await fetch('/api/speech-token')
  if (!response.ok) throw new Error(response.status === 503 ? 'Voice questions are not set up' : 'Speech service unavailable')
  return response.json()
}

/**
 * Listen for one question. Resolves with the text heard ('' if nothing). Aborting the signal
 * (the viewer pressed stop) or reaching the safety limit ends listening and returns what was heard so far.
 */
export async function listenOnce(onPartial: (text: string) => void, signal: AbortSignal, language = 'en-US'): Promise<string> {
  const { token, region } = await fetchToken()
  if (signal.aborted) return ''
  const config = SpeechConfig.fromAuthorizationToken(token, region)
  config.speechRecognitionLanguage = language
  const recognizer = new SpeechRecognizer(config, AudioConfig.fromDefaultMicrophoneInput())
  let heardSoFar = ''
  recognizer.recognizing = (_sender, event) => {
    heardSoFar = event.result.text
    onPartial(heardSoFar)
  }

  let timer: ReturnType<typeof setTimeout> | undefined
  const finishEarly = new Promise<string>((resolve) => {
    const stop = () => resolve(heardSoFar)
    signal.addEventListener('abort', stop, { once: true })
    timer = setTimeout(stop, MAX_LISTEN_MS)
  })
  const recognized = new Promise<string>((resolve, reject) =>
    recognizer.recognizeOnceAsync(
      (result) => resolve(result.reason === ResultReason.RecognizedSpeech ? result.text : heardSoFar),
      (error) => reject(new Error(error)),
    ),
  )

  try {
    return await Promise.race([recognized, finishEarly])
  } finally {
    clearTimeout(timer)
    recognizer.close()
  }
}
