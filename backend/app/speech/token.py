"""Short-lived Azure Speech tokens for the browser's microphone (#21).

The browser streams the viewer's voice straight to Azure Speech (it shows the words as they
speak). It must never see our key, so the server exchanges the key for a 10-minute token.
One token is shared and reused for 9 minutes, which also caps how often anyone can ask.
"""
import time

import httpx

from app.config import settings

TOKEN_LIFETIME = 9 * 60  # Azure tokens last 10 minutes; refresh a minute early

_cache: dict[str, float | str] = {"token": "", "expires": 0.0}


async def speech_token(client: httpx.AsyncClient | None = None) -> str:
    if _cache["token"] and time.monotonic() < float(_cache["expires"]):
        return str(_cache["token"])
    url = f"https://{settings.azure_speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    async with client or httpx.AsyncClient(timeout=5.0) as http:
        response = await http.post(url, headers={"Ocp-Apim-Subscription-Key": settings.azure_speech_key})
        response.raise_for_status()
    _cache.update(token=response.text, expires=time.monotonic() + TOKEN_LIFETIME)
    return response.text
