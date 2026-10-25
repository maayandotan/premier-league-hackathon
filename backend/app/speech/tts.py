"""Text to speech with Azure AI Speech (#19), moved from the spike in spikes/speech/.

- Caller: en-US-DavisNeural, using the voice's own styles: excited for build-up, shouting for
  big moments. We never speed voices up (it sounded bad).
- Analyst: en-GB-Ryan HD, a British voice that takes its tone from the text (no styles), calm.
Both were picked by ear from samples of the voices our Speech tier offers (Oct 2026).
Returns MP3 bytes: small enough to send to the browser over the WebSocket.
"""
import logging
from xml.sax.saxutils import escape

import httpx

from app.config import settings

log = logging.getLogger(__name__)

VOICES = {"caller": "en-US-DavisNeural", "analyst": "en-GB-Ryan:DragonHDLatestNeural"}
LOCALES = {"caller": "en-US", "analyst": "en-GB"}
CALLER_STYLES = {1: "excited", 2: "shouting"}  # excitement level -> Davis's built-in style
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"


def speech_enabled() -> bool:
    return settings.use_speech and bool(settings.azure_speech_key)


def ssml(speaker: str, text: str, excitement: int) -> str:
    body = escape(text)
    style = CALLER_STYLES.get(excitement) if speaker == "caller" else None
    if style:
        body = f'<mstts:express-as style="{style}">{body}</mstts:express-as>'
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{LOCALES[speaker]}">'
        f'<voice name="{VOICES[speaker]}">{body}</voice></speak>'
    )


class Speech:
    """One HTTP connection to Azure Speech, reused for the whole match."""

    def __init__(self) -> None:
        self.url = f"https://{settings.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self.client = httpx.AsyncClient(timeout=5.0)

    async def synthesize(self, speaker: str, text: str, excitement: int) -> bytes | None:
        """MP3 audio for one line, or None if Speech is unavailable (the text still shows)."""
        try:
            response = await self.client.post(self.url, content=ssml(speaker, text, excitement).encode(),
                                              headers={
                "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
                "User-Agent": "match-intelligence",
            })
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as error:
            log.warning("speech failed: %s", error)
            return None

    async def close(self) -> None:
        await self.client.aclose()
