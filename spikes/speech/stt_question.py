"""Spike for issue #3: transcribe a viewer's spoken question with Azure Speech (speech-to-text).

With no argument, it first synthesizes sample questions with a TTS voice, then
transcribes them back, to measure round-trip latency without a microphone.

Usage:  python spikes/speech/stt_question.py [recording.wav] [--lang en-US|he-IL]
        The recording must be 16 kHz, 16-bit, mono PCM WAV.
"""
import argparse
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["AZURE_SPEECH_KEY"]
REGION = os.environ["AZURE_SPEECH_REGION"]
STT_URL = f"https://{REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
TTS_URL = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
OUT_DIR = Path(__file__).parent / "out"

SAMPLES = {
    "en-US": ("en-US-JennyNeural", "Why was that a foul?"),
    "he-IL": ("he-IL-HilaNeural", "למה זה היה נבדל?"),
}


def make_sample(lang: str) -> Path:
    voice, text = SAMPLES[lang]
    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang}">'
        f'<voice name="{voice}">{text}</voice></speak>'
    )
    resp = requests.post(
        TTS_URL,
        headers={
            "Ocp-Apim-Subscription-Key": KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
            "User-Agent": "pl-hackathon-speech-spike",
        },
        data=ssml.encode("utf-8"),
        timeout=30,
    )
    resp.raise_for_status()
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"question_{lang}.wav"
    path.write_bytes(resp.content)
    return path


def transcribe(path: Path, lang: str) -> tuple[str, float]:
    start = time.perf_counter()
    resp = requests.post(
        STT_URL,
        params={"language": lang, "format": "simple"},
        headers={
            "Ocp-Apim-Subscription-Key": KEY,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        },
        data=path.read_bytes(),
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("DisplayText", f"<{body.get('RecognitionStatus')}>"), time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", nargs="?", type=Path)
    parser.add_argument("--lang", choices=SAMPLES)
    args = parser.parse_args()

    langs = [args.lang] if args.lang else list(SAMPLES)
    for lang in langs:
        path = args.recording or make_sample(lang)
        text, seconds = transcribe(path, lang)
        print(f"{lang}: {seconds:.2f}s  ->  {text}")


if __name__ == "__main__":
    main()
