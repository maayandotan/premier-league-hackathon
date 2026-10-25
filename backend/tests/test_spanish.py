"""Spanish commentary: Davis writes Spanish, Roy is checked in English and then translated."""
import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.agents.analyst import Analyst
from app.agents.caller import Caller, template_line
from app.agents.language import FIXED, Translator, check_translation
from app.agents.pipeline import CommentaryPipeline
from app.agents.qa import NOT_SURE
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent, ShotDetails
from app.main import app
from app.speech.tts import ssml
from app.stats.engine import StatsEngine
from app.stats.ranker import Moment

HOME, AWAY = "Northbridge FC", "Westvale United"


class Scripted:
    def __init__(self, *texts):
        self.texts, self.inputs = list(texts), []

    async def run(self, prompt, **_):
        self.inputs.append(prompt)
        return SimpleNamespace(text=self.texts.pop(0) if self.texts else "")


def goal() -> MatchEvent:
    return MatchEvent(id="g", index=1, period=2, minute=88, second=0, type="Shot", team=HOME,
                      player="M. Ferro", location=(108.0, 40.0), shot=ShotDetails(outcome="Goal"))


def test_a_translation_keeps_every_number_and_name():
    source = "Northbridge FC have 65% of the ball and Ferro's chance was worth 0.4 xG."
    good = "Northbridge FC tiene el 65% del balón y la ocasión de Ferro valía 0,4 xG."
    assert check_translation(source, good, [HOME, "Ferro"]) == []  # a decimal comma is the same number
    assert check_translation(source, good.replace("65", "56"), [HOME, "Ferro"])  # a changed number
    assert check_translation(source, good.replace("Ferro", "el delantero"), [HOME, "Ferro"])  # a lost name


def test_a_bad_translation_falls_back_to_the_checked_english():
    translator = Translator(use_model=False, names=[HOME])
    translator.agent = Scripted("Northbridge FC tiene el 75% del balón.")
    assert asyncio.run(translator.to_spanish("Northbridge FC have 65% of the ball.")) is None
    translator.agent = Scripted("Northbridge FC tiene el 65% del balón.")
    assert asyncio.run(translator.to_spanish("Northbridge FC have 65% of the ball.")) == \
        "Northbridge FC tiene el 65% del balón."
    assert asyncio.run(Translator(use_model=False).to_spanish(NOT_SURE)) == FIXED[NOT_SURE]  # no model needed


def test_davis_writes_spanish_and_his_templates_are_spanish():
    stats = StatsEngine(HOME, AWAY)
    stats.update(goal())
    moment = Moment(score=10, reason="late go-ahead goal", kind="goal", quiet=True)
    assert template_line(goal(), moment, stats, "es") == "¡GOL! ¡M. Ferro! ¡1-0!"
    chance = Moment(score=7, reason="big chance, saved", kind="chance", quiet=False)
    assert template_line(goal(), chance, stats, "es") == "M. Ferro... ¡ocasión clara!"

    caller = Caller(use_model=False)
    caller.agent = SimpleNamespace(run=Scripted().run)
    viewer = ViewerProfile()
    viewer.set_language("es")
    text, _, source = asyncio.run(caller.call(goal(), moment, stats, viewer))
    assert source == "template" and text.startswith("¡GOL!")  # the model gave nothing: Spanish template


def test_roy_is_checked_in_english_then_translated():
    stats = StatsEngine(HOME, AWAY)
    viewer = ViewerProfile()
    viewer.set_language("es")
    analyst = Analyst(stats, {}, use_model=False)
    analyst.agent = Scripted("Northbridge FC finally break through.")
    pipeline = CommentaryPipeline(stats, Caller(use_model=False), analyst, viewer)
    pipeline.translator.agent = Scripted("Northbridge FC por fin abre el marcador.")
    stats.update(goal())
    line = asyncio.run(pipeline.analyse(goal(), Moment(score=10, reason="goal", kind="goal", quiet=True)))
    assert (line.text, line.language) == ("Northbridge FC por fin abre el marcador.", "es")
    assert "finally break through" in pipeline.match_log.entries[-1].text  # callbacks search English

    analyst.agent = Scripted("Northbridge FC lead.")
    pipeline.translator.agent = Scripted("")  # translation failed: the checked English line, English voice
    pipeline._last_analysis_at = None
    line = asyncio.run(pipeline.analyse(goal(), Moment(score=10, reason="goal", kind="goal", quiet=True)))
    assert (line.text, line.language) == ("Northbridge FC lead.", "en")


def test_spanish_lines_get_spanish_voices():
    goal_call = ssml("caller", "¡GOL!", 2, "es")
    assert "es-MX-Alejo" in goal_call and 'style="shouting"' in goal_call
    assert "es-MX-Jorge" in ssml("analyst", "Hola.", 0, "es")
    assert "en-US-DavisNeural" in ssml("caller", "GOAL!", 2)  # English stays the default


def test_the_match_in_spanish_end_to_end():
    with TestClient(app).websocket_connect("/ws/match?speed=10000&lang=es") as ws:
        lines = []
        while (message := ws.receive_json())["type"] != "end":
            if message["type"] == "commentary":
                lines.append(message["line"])
    callers = [line for line in lines if line["speaker"] == "caller"]
    assert callers and all(line["language"] == "es" for line in callers)
    assert any(line["text"].startswith("¡GOL!") for line in callers)
