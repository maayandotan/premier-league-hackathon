"""Spike for issue #3: two-voice commentary with Azure Speech (text-to-speech).

Synthesizes a short caller/analyst exchange, one line at a time (the way the
Producer's audio queue will work), and reports latency per line.

Usage:  python spikes/speech/tts_dialogue.py [--lang en|he] [--voices caller,analyst] [--name file]
Output: spikes/speech/out/<lang>_dialogue.mp3  (git-ignored)
"""
import argparse
import os
import time
from pathlib import Path
from xml.sax.saxutils import escape

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["AZURE_SPEECH_KEY"]
REGION = os.environ["AZURE_SPEECH_REGION"]
TTS_URL = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
OUT_DIR = Path(__file__).parent / "out"

# Each line: (speaker, style or None, text). Fictional teams and players only (DATA_POLICY.md).
SCRIPTS = {
    "en": [
        ("caller", "excited", "Arlo, through ball, Ferro is in behind... he shoots... GOAL! Northbridge lead!"),
        ("analyst", None, "And that one came against the run of play. Westvale had sixty-eight percent of the ball in the last fifteen minutes."),
        ("caller", None, "So was that a moment of brilliance, or a defensive mistake?"),
        ("analyst", None, "Bit of both. The pass broke two lines, which only happens about four percent of the time. But the shot itself was worth just nine percent."),
        ("caller", "cheerful", "A finish to remember, then. Northbridge one, Westvale nil."),
    ],
    "he": [
        ("caller", None, "ארלו, כדור עומק, פרו פורץ... בועט... גול! נורת'ברידג' ביתרון!"),
        ("analyst", None, "והגול הזה הגיע נגד מהלך המשחק. לווסטוויל היו שישים ושמונה אחוז החזקה ברבע השעה האחרונה."),
        ("caller", None, "אז זה היה רגע של גאונות, או טעות בהגנה?"),
        ("analyst", None, "קצת משניהם. המסירה שברה שני קווים, וזה קורה רק בכארבעה אחוז מהמקרים."),
    ],
}

DEFAULT_VOICES = {
    "en": ("en-US-GuyNeural", "en-GB-RyanNeural"),
    "he": ("he-IL-AvriNeural", "he-IL-HilaNeural"),
}
LOCALES = {"en": "en-US", "he": "he-IL"}


def ssml(voice: str, text: str, style: str | None, locale: str) -> str:
    body = escape(text)
    if style:
        body = f'<mstts:express-as style="{style}">{body}</mstts:express-as>'
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{locale}">'
        f'<voice name="{voice}">{body}<break time="250ms"/></voice></speak>'
    )


def synthesize(doc: str) -> tuple[bytes, float, float]:
    """Return (audio, seconds to first byte, total seconds)."""
    start = time.perf_counter()
    resp = requests.post(
        TTS_URL,
        headers={
            "Ocp-Apim-Subscription-Key": KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "pl-hackathon-speech-spike",
        },
        data=doc.encode("utf-8"),
        stream=True,
        timeout=30,
    )
    resp.raise_for_status()
    chunks, first = [], None
    for chunk in resp.iter_content(4096):
        if first is None:
            first = time.perf_counter() - start
        chunks.append(chunk)
    return b"".join(chunks), first or 0.0, time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=SCRIPTS, default="en")
    parser.add_argument("--voices", help="caller,analyst voice names")
    parser.add_argument("--name", help="output file name (without .mp3)")
    args = parser.parse_args()

    caller, analyst = args.voices.split(",") if args.voices else DEFAULT_VOICES[args.lang]
    voices = {"caller": caller, "analyst": analyst}
    OUT_DIR.mkdir(exist_ok=True)

    audio = b""
    print(f"{'speaker':8} {'first byte':>10} {'total':>7}  text")
    for speaker, style, text in SCRIPTS[args.lang]:
        clip, first, total = synthesize(ssml(voices[speaker], text, style, LOCALES[args.lang]))
        audio += clip  # MP3 frames concatenate cleanly for a quick listen
        print(f"{speaker:8} {first:9.2f}s {total:6.2f}s  {text[:60]}")

    out = OUT_DIR / f"{args.name or args.lang + '_dialogue'}.mp3"
    out.write_bytes(audio)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
