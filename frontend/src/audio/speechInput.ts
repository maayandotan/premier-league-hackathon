/**
 * The viewer's microphone (#21): streams their voice to Azure Speech and returns the text.
 * Words appear while they speak (onPartial); recognition stops by itself at the end of the
 * sentence. The browser never sees our key: it gets a 10-minute token from /api/speech-token.
 */
import {
  AudioConfig,
  ResultReason,
  SpeechConfig,
  SpeechRecognizer,
} from 'microsoft-cognitiveservices-speech-sdk'

interface Token {
  token: string
  region: string
}

async function fetchToken(): Promise<Token> {
  const response = await fetch('/api/speech-token')
  if (!response.ok) throw new Error(response.status === 503 ? 'Voice questions are not set up' : 'Speech service unavailable')
  return response.json()
}

/** Listen for one question. Resolves with the final text ('' if nothing was heard). */
export async function listenOnce(onPartial: (text: string) => void, language = 'en-US'): Promise<string> {
  const { token, region } = await fetchToken()
  const config = SpeechConfig.fromAuthorizationToken(token, region)
  config.speechRecognitionLanguage = language
  const recognizer = new SpeechRecognizer(config, AudioConfig.fromDefaultMicrophoneInput())
  recognizer.recognizing = (_sender, event) => onPartial(event.result.text)

  try {
    const result = await new Promise<{ reason: ResultReason; text: string }>((resolve, reject) =>
      recognizer.recognizeOnceAsync(resolve, (error) => reject(new Error(error))),
    )
    return result.reason === ResultReason.RecognizedSpeech ? result.text : ''
  } finally {
    recognizer.close()
  }
}
