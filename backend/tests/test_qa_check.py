"""Q&A answers are checked against what the tools returned for that question (#17)."""
import asyncio
from types import SimpleNamespace

import pytest

from app.agents.checker import check_answer, recorded, recording
from app.agents.qa import NOT_SURE, QuestionAnswerer, build_qa_tools
from app.agents.viewer import ViewerProfile
from app.events.models import MatchEvent, PassDetails
from app.stats.engine import StatsEngine

HOME, AWAY = "Northbridge FC", "Westvale United"
PICTURE = {"possession": {HOME: 48.8, AWAY: 51.2}, "possession_last_10_min": {HOME: 64.6, AWAY: 35.4},
           "xg": {HOME: 3.12, AWAY: 1.89}, "shots": {HOME: 11, AWAY: 12},
           "shots_last_10_min": {HOME: 1, AWAY: 5}}
SHOT = {"xg": 0.188, "label": "half chance"}


def stats() -> StatsEngine:
    return StatsEngine(HOME, AWAY)


def test_tools_record_what_they_returned_per_question():
    tool = recorded(lambda: {"x": 1})

    async def ask(value):
        inner = recorded(lambda: {"value": value})
        with recording() as seen:
            await asyncio.sleep(0)
            await asyncio.to_thread(inner)  # the framework runs sync tools in a thread
            return seen

    async def two_viewers():
        return await asyncio.gather(ask(1), ask(2))

    first, second = asyncio.run(two_viewers())
    assert first == [{"value": 1}] and second == [{"value": 2}]  # no mixing between questions
    assert tool() == {"x": 1}  # outside a question, tools just work


def test_wrapped_tools_keep_their_names_for_the_model():
    names = [t.__name__ for t in build_qa_tools(stats(), [], {})]
    assert {"get_events_before", "get_key_moments", "get_rule", "get_tactic", "get_patterns",
            "get_match_story", "get_league_table", "get_club_season", "get_player", "get_match_picture",
            "get_shot_quality", "get_pass_rarity",
            "show_team_results_by_goals", "show_player_scoring_by_time", "show_xg_race"} == set(names)


@pytest.mark.parametrize("answer", [
    "Northbridge FC had 65% of the ball in the last 10 minutes.",
    "Westvale have created 1.89 xG to Northbridge's 3.12.",
    "Northbridge FC: 64.6 percent of the ball lately.",
    "Northbridge took 11 shots, Westvale 12.",
])
def test_true_answers_pass_with_normal_rounding(answer):
    assert check_answer(answer, [PICTURE], stats(), set()) == []


@pytest.mark.parametrize("answer, problem", [
    ("Westvale United had 65% of the ball.", "65 belongs to Northbridge FC, not Westvale United"),
    ("Northbridge's xG is 1.89.", "1.89 belongs to Westvale United"),
    ("They've had 58% of the ball.", "the number 58 didn't come from your tools"),
    ("Northbridge FC has more shots (11).", "is wrong in the whole match"),
    ("In the last 10 minutes Northbridge took more shots.", "is wrong in the last 10 minutes"),
    ("Lately Westvale have had more of the ball.", "is wrong in the last 10 minutes"),
    ("That was an excellent chance.", "without get_shot_quality"),
    ("That goal likely decided the match.", "is a guess"),
])
def test_wrong_answers_are_caught(answer, problem):
    assert problem in "; ".join(check_answer(answer, [PICTURE], stats(), set()))


def test_numbers_from_the_question_are_fine():
    assert check_answer("Yes, 3 corners so far.", [], stats(), {"3"}) == []


class ScriptedAgent:
    """Calls the real (recorded) tool, then answers with the next scripted line."""

    def __init__(self, tool, lines):
        self.tool, self.lines, self.inputs = tool, lines, []

    async def run(self, prompt):
        self.inputs.append(prompt)
        self.tool()
        return SimpleNamespace(text=self.lines[min(len(self.inputs), len(self.lines)) - 1])


def answerer_with(lines) -> tuple[QuestionAnswerer, ScriptedAgent]:
    st = stats()
    for i in range(10):
        st.update(MatchEvent(id=f"p{i}", index=i, period=1, minute=5, second=i, type="Pass", team=HOME,
                             location=(40.0, 40.0), **{"pass": PassDetails(end_location=(45.0, 40.0))}))
    qa = QuestionAnswerer(st, [], {}, use_model=False)
    picture = {t.__name__: t for t in build_qa_tools(st, [], {})}["get_match_picture"]
    qa.agent = ScriptedAgent(picture, lines)
    return qa, qa.agent


def test_a_wrong_answer_gets_one_retry():
    qa, agent = answerer_with(["Westvale have had 100% of the ball.",
                               "Northbridge have had 100% of the ball."])
    answer = asyncio.run(qa.answer("Who has the ball?", 5, 30, ViewerProfile()))
    assert answer == "Northbridge have had 100% of the ball."
    assert "WRONG: 100 belongs to Northbridge FC, not Westvale United" in agent.inputs[1]


def test_still_wrong_means_an_honest_ask_again():
    qa, _ = answerer_with(["Westvale have had 100% of the ball."])
    assert asyncio.run(qa.answer("Who has the ball?", 5, 30, ViewerProfile())) == NOT_SURE


def test_chance_words_must_match_the_shot_quality_label():
    assert check_answer("A decent chance, well taken.", [PICTURE, SHOT], stats(), set()) == []
    problems = check_answer("A great chance, well taken.", [PICTURE, SHOT], stats(), set())
    assert problems == ["the chance was a half chance, not a big chance"]


def test_right_comparisons_pass():
    answer = ("Westvale have taken more shots overall. In the last 10 minutes Westvale took more shots "
              "too. Lately Northbridge have had more of the ball.")
    assert check_answer(answer, [PICTURE], stats(), set()) == []


def test_whole_match_and_last_ten_minutes_in_one_sentence():
    answer = ("Westvale have had more possession overall, but in the last 10 minutes Northbridge have had "
              "more of the ball.")
    assert check_answer(answer, [PICTURE], stats(), set()) == []
    flipped = "Northbridge have had more possession overall, but lately Westvale have had more of the ball."
    assert len(check_answer(flipped, [PICTURE], stats(), set())) == 2


def test_time_words_belong_to_the_nearest_comparison():
    """A real answer that a clause-wide rule wrongly rejected."""
    answer = ("Northbridge FC is winning 2-1. Even though Westvale United has had more shots recently, "
              "Northbridge has had better chances overall and more possession in the last 10 minutes.")
    assert check_answer(answer, [PICTURE], stats(), {"2", "1"}) == []
