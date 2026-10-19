from fastapi.testclient import TestClient

from app.main import app
from app.speech.tts import speech_enabled, ssml


def test_caller_voice_style_follows_excitement():
    assert 'style="shouting"' in ssml("caller", "GOAL!", 2)
    assert 'style="excited"' in ssml("caller", "Ferro... into the box...", 1)
    calm = ssml("caller", "Foul in midfield.", 0)
    assert "express-as" not in calm and "en-US-GuyNeural" in calm


def test_analyst_is_sonia_and_always_calm():
    analyst = ssml("analyst", "That came against the run of play.", 2)
    assert "en-GB-SoniaNeural" in analyst and "express-as" not in analyst


def test_text_is_escaped_for_ssml():
    assert "Q&amp;A &lt;3" in ssml("caller", "Q&A <3", 0)


def test_speech_is_off_in_tests():
    assert not speech_enabled()


def test_crowd_audio_is_served():
    client = TestClient(app)
    for name in ("crowd_ambience_loop.wav", "crowd_goal_roar.wav"):
        response = client.get(f"/static/audio/{name}")
        assert response.status_code == 200 and response.content[:4] == b"RIFF"
