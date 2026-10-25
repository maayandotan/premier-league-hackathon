from fastapi.testclient import TestClient

from app.main import app
from app.speech.tts import speech_enabled, ssml


def test_caller_voice_style_follows_excitement():
    assert 'style="shouting"' in ssml("caller", "GOAL!", 2)
    assert 'style="excited"' in ssml("caller", "Ferro... into the box...", 1)
    calm = ssml("caller", "Foul in midfield.", 0)
    assert "express-as" not in calm and "en-US-DavisNeural" in calm


def test_analyst_is_roy_and_always_calm():
    analyst = ssml("analyst", "That came against the run of play.", 2)
    assert "en-GB-Ryan:DragonHDLatestNeural" in analyst and "express-as" not in analyst


def test_text_is_escaped_for_ssml():
    assert "Q&amp;A &lt;3" in ssml("caller", "Q&A <3", 0)


def test_speech_is_off_in_tests():
    assert not speech_enabled()


def test_crowd_audio_is_served():
    client = TestClient(app)
    for name in ("crowd_ambience_loop.wav", "crowd_goal_roar.wav"):
        response = client.get(f"/static/audio/{name}")
        assert response.status_code == 200 and response.content[:4] == b"RIFF"


def test_speech_token_needs_speech_configured():
    assert TestClient(app).get("/api/speech-token").status_code == 503  # speech is off in tests


def test_speech_token_is_cached(monkeypatch):
    import asyncio

    import httpx

    from app.speech import token as token_module

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-key"
        return httpx.Response(200, text=f"token-{len(calls)}")

    monkeypatch.setattr(token_module.settings, "azure_speech_key", "test-key")
    monkeypatch.setattr(token_module, "_cache", {"token": "", "expires": 0.0})

    def client():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    assert asyncio.run(token_module.speech_token(client())) == "token-1"
    assert asyncio.run(token_module.speech_token(client())) == "token-1"  # reused, not re-issued
    assert len(calls) == 1
