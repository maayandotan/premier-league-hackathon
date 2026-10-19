"""Spike for issue #3: two-voice commentary with Azure Speech (text-to-speech).

Synthesizes a short caller/analyst exchange, one line at a time (the way the
Producer's audio queue will work), reports latency per line, and can mix in
stadium crowd sound with a roar on the goal.

Usage:  python spikes/speech/tts_dialogue.py [--lang en|he] [--voices caller,analyst]
                                             [--name file] [--flat] [--crowd]
Output: spikes/speech/out/<name>.wav  (git-ignored)
"""
import argparse
import io
import json
import os
import time
import wave
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import requests
from dotenv import load_dotenv

import crowd

load_dotenv()
KEY = os.environ["AZURE_SPEECH_KEY"]
REGION = os.environ["AZURE_SPEECH_REGION"]
TTS_URL = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
VOICES_URL = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list"
OUT_DIR = Path(__file__).parent / "out"
SAMPLE_RATE = 24000

# Each line: (speaker, excitement 0-2, text). Fictional teams and players only (DATA_POLICY.md).
# The caller builds up over several short lines; that crescendo is what sells a goal.
SCRIPTS = {
    "en": [
        ("caller", 1, "Arlo, through ball, Ferro is in behind..."),
        ("caller", 2, "he shoots... GOAL! Northbridge lead!"),
        ("analyst", 0, "And that one came against the run of play. Westvale had sixty-eight percent of the ball in the last fifteen minutes."),
        ("caller", 0, "So was that a moment of brilliance, or a defensive mistake?"),
        ("analyst", 0, "Bit of both. The pass broke two lines, which only happens about four percent of the time. But the shot itself was worth just nine percent."),
        ("caller", 1, "A finish to remember, then. Northbridge one, Westvale nil."),
    ],
    "he": [
        ("caller", 1, "ארלו, כדור עומק, פרו פורץ..."),
        ("caller", 2, "בועט... גול! נורת'ברידג' ביתרון!"),
        ("analyst", 0, "והגול הזה הגיע נגד מהלך המשחק. לווסטוויל היו שישים ושמונה אחוז החזקה ברבע השעה האחרונה."),
        ("caller", 0, "אז זה היה רגע של גאונות, או טעות בהגנה?"),
        ("analyst", 0, "קצת משניהם. המסירה שברה שני קווים, וזה קורה רק בכארבעה אחוז מהמקרים."),
    ],
}

DEFAULT_VOICES = {
    "en": ("en-US-GuyNeural", "en-GB-SoniaNeural"),
    "he": ("he-IL-AvriNeural", "he-IL-HilaNeural"),
}

# Preferred built-in style per excitement level, best first. Voices without a
# matching style fall back to a little extra volume, never speed.
STYLES_BY_LEVEL = {1: ["excited", "cheerful"], 2: ["shouting", "excited", "cheerful"]}


def voice_catalog() -> dict[str, dict]:
    cache = OUT_DIR / "voices.json"
    if not cache.exists():
        resp = requests.get(VOICES_URL, headers={"Ocp-Apim-Subscription-Key": KEY}, timeout=30)
        resp.raise_for_status()
        cache.write_text(resp.text)
    return {v["ShortName"]: v for v in json.loads(cache.read_text())}


def ssml(voice: dict, text: str, excitement: int) -> str:
    body = escape(text)
    styles = voice.get("StyleList") or []
    style = next((s for s in STYLES_BY_LEVEL.get(excitement, []) if s in styles), None)
    if style:
        body = f'<mstts:express-as style="{style}">{body}</mstts:express-as>'
    elif excitement == 2:
        body = f'<prosody volume="+30%">{body}</prosody>'
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{voice["Locale"]}">'
        f'<voice name="{voice["ShortName"]}">{body}</voice></speak>'
    )


def synthesize(doc: str) -> tuple[np.ndarray, float, float]:
    """Return (samples in [-1, 1], seconds to first byte, total seconds)."""
    start = time.perf_counter()
    resp = requests.post(
        TTS_URL,
        headers={
            "Ocp-Apim-Subscription-Key": KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
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
    with wave.open(io.BytesIO(b"".join(chunks))) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768, first or 0.0, time.perf_counter() - start


def at_level(samples: np.ndarray, rms_db: float) -> np.ndarray:
    """Scale samples so their RMS loudness is rms_db dBFS."""
    rms = np.sqrt(np.mean(samples**2)) + 1e-9
    return samples * (10 ** (rms_db / 20) / rms)


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=SCRIPTS, default="en")
    parser.add_argument("--voices", help="caller,analyst voice names")
    parser.add_argument("--name", help="output file name (without .wav)")
    parser.add_argument("--flat", action="store_true", help="ignore excitement, for comparison")
    parser.add_argument("--crowd", action="store_true", help="mix in crowd ambience and a goal roar")
    parser.add_argument("--synthetic-crowd", action="store_true", help="use the procedural crowd, not the recordings")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    catalog = voice_catalog()
    caller, analyst = args.voices.split(",") if args.voices else DEFAULT_VOICES[args.lang]
    voices = {"caller": catalog[caller], "analyst": catalog[analyst]}

    gap = np.zeros(int(0.25 * SAMPLE_RATE), dtype=np.float32)
    lead_in = np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32)  # a moment of crowd before anyone speaks
    speech, goal_at = [lead_in], None
    print(f"{'speaker':8} {'first byte':>10} {'total':>7}  text")
    for speaker, excitement, text in SCRIPTS[args.lang]:
        level = 0 if args.flat else excitement
        clip, first, total = synthesize(ssml(voices[speaker], text, level))
        if level == 2 and goal_at is None:
            goal_at = sum(len(s) for s in speech)
        speech += [clip, gap]
        print(f"{speaker:8} {first:9.2f}s {total:6.2f}s  {text[:60]}")

    mix = np.concatenate(speech + [np.zeros(int(2.5 * SAMPLE_RATE), dtype=np.float32)])
    if args.crowd:
        seconds = len(mix) / SAMPLE_RATE
        bed = None if args.synthetic_crowd else crowd.real_ambience(seconds, SAMPLE_RATE)
        if bed is None:
            bed = crowd.ambience(seconds, SAMPLE_RATE)
        mix += at_level(bed[: len(mix)], -33)  # about 15 dB under the commentary
        if goal_at is not None:
            roar = None if args.synthetic_crowd else crowd.real_roar(SAMPLE_RATE)
            if roar is None:
                roar = crowd.roar(SAMPLE_RATE)
            roar = at_level(roar, -21)
            # Start the swell during "he shoots..." so it peaks under "GOAL!"
            start = max(0, goal_at - int(1.0 * SAMPLE_RATE))
            end = min(len(mix), start + len(roar))
            mix[start:end] += roar[: end - start]
    mix = np.tanh(mix * 1.1)  # gentle limiter so the roar never clips

    out = OUT_DIR / f"{args.name or args.lang + '_dialogue'}.wav"
    write_wav(out, mix)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
