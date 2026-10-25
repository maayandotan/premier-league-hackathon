# Football tactics playbook

The football knowledge our analyst (Roy) and the Q&A agent explain from. Written by us, in our own words, from general football knowledge (see [Further reading](#further-reading)); nothing is copied from another source.

**How the agents use it.** Each concept has the same parts, so code can load just the section a moment needs into an agent's context:

- **What it is**: the idea in plain words.
- **In our data**: what the event feed can actually show, and which stat or detector measures it. "Today" means the stats engine has it now; "#48" means a detector still to build ([Tactical Intelligence Engine](https://github.com/maayandotan/premier-league-hackathon/issues/48)). The agents are told only the "Today" part: for a concept with none, they explain the idea but can't say whether a team is doing it.
- **Say it**: one line per viewer level, as a model of tone and depth (not a script).
- **Don't claim**: what event data can't support. The agents can't see the video.

**The numbers in the examples are made up** to show tone and depth. An agent never repeats them: every number it says comes from a tool, for this match, right now.

## What our data can and can't show

We have **events**: who did what, where (x, y on a 120 × 80 pitch, from the acting team's side), when, and the outcome: passes with their end point, carries, shots, fouls, cards, recoveries, set pieces, substitutions. Plus what the stats engine computes from them: score, xG, possession (share of passes), momentum (who has been more dangerous), tempo, progressive passes.

We **don't** have the positions of players without the ball, the shape of the teams, who was marking whom, runs off the ball, body shape, the referee's view, or anything only video shows. So:

- Say what the events show: "five times down the right in ten minutes", "won it back and shot within ten seconds".
- Never describe what nobody tracked: "the full-back was caught too high", "he timed his run perfectly", "the defender lost his man".
- Never judge a decision ("that was never a penalty"). Explain the rule and what happened.
- A pattern needs enough examples before it's claimed. One cross is not "a crossing game".

---

## Counter-attack and transitions

**What it is.** The moment the ball changes hands, both teams are briefly out of shape. A counter-attack uses that moment: win the ball and go forward fast, before the opponents can get back behind the ball. Teams that defend deep and break quickly rely on it.

**In our data.** Today: quick attacks per team in the last 15 minutes (the ball won, then a shot or a box entry within 12 seconds), from `get_patterns`; and which attacks came `From Counter` in the events.

**Say it.**
- Beginner: "They won the ball and ran at goal before the other team could get back."
- Fan: "Westvale broke at speed the moment they won it: that's their third quick counter this half."
- Analyst: "Another transition chance: recovery to shot in under ten seconds, while Northbridge were still out of shape."

**Don't claim.** How many defenders were back, or that a player "switched off". We don't see players without the ball.

## Pressing and counter-pressing

**What it is.** Pressing is going after the ball high up the pitch instead of waiting for the opponents to come forward. Counter-pressing (gegenpressing) is pressing immediately after losing the ball, to win it back while the other team is still disorganised. A ball won high up is close to the opponent's goal, so it often leads to a chance.

**In our data.** Today: balls won in the opponent's half per team in the last 15 minutes, compared with the other team (`get_patterns`); claimed only when it's at least 6 and double the other side's. #48: PPDA (opponent passes allowed per defensive action).

**Say it.**
- Beginner: "They're chasing the ball right up near the other team's goal, so it's hard to play out."
- Fan: "Westvale are winning it high up the pitch: four turnovers in Northbridge's half in ten minutes."
- Analyst: "The press is working: four high regains in ten minutes, and Northbridge are being forced long."

**Don't claim.** Pressing "triggers", who started the press, or a team's defensive line height. Those need tracking data.

## Possession versus danger

**What it is.** Having the ball is not the same as being on top. A team can pass it around for minutes without creating anything ("sterile possession"), while the other side defends deep and is more dangerous on the break. Territory (how much of the play happens in the opponent's final third) and chance quality tell more than possession alone.

**In our data.** Today: possession (overall and last 10 minutes), momentum (who has been more dangerous), shots and xG, `get_run_of_play`, which reports the ball and the danger separately, and field tilt (a team's share of the final-third passes in the last 15 minutes, claimed at 75%+, from `get_patterns`).

**Say it.**
- Beginner: "Northbridge have had the ball more, but Westvale have had the better chances."
- Fan: "Northbridge have 65% of the ball lately, but it's Westvale who look dangerous."
- Analyst: "65% possession in the last ten for Northbridge, yet the threat is all Westvale: classic sterile possession."

**Don't claim.** That one team is "dominating" just because it has more of the ball. This exact mistake happened (see lesson 10 in [AGENTS.md](../AGENTS.md)).

## Attacking channels and overloads

**What it is.** Teams often attack more down one side: to target a weaker defender, to use a quick winger, or to overload one flank with extra players and then switch play to the other side where there's space. The pitch is often described in five vertical lanes: the two wings, the two "half-spaces" between wing and centre, and the centre.

**In our data.** Today: final-third entries by left, centre and right in the last 15 minutes (`get_patterns`; claimed with at least 6 entries and 60% on one side), and for a goal, which side its attack came down compared with the whole match. Synthetic scenarios can give a team a favourite side, so the pattern is really there.

**Say it.**
- Beginner: "They keep attacking down the right side. That's where they think the other team is weakest."
- Fan: "Six times down the right in ten minutes: Northbridge have clearly found something there."
- Analyst: "The right channel is the plan: six final-third entries there in ten minutes, two on the left."

**Don't claim.** Why a side is targeted ("the left-back is struggling") unless the events show it, e.g. repeated duels lost in that area.

## Build-up: playing out from the back versus going direct

**What it is.** Some teams build attacks patiently with short passes from the goalkeeper and defenders, drawing opponents forward to create space behind them. Others go direct: long balls forward to a target or into space, skipping midfield. Neither is better; it depends on the players and the score.

**In our data.** Today: recent events show individual long balls and how goal kicks are taken; no totals yet. #48: "directness" detector: forward progress per possession and passes per possession.

**Say it.**
- Beginner: "They're passing it short from the back, being patient instead of kicking it long."
- Fan: "Northbridge have stopped playing it short: nearly every goal kick is going long now."
- Analyst: "Much more direct since the red card: fewer passes per possession and far more long balls."

**Don't claim.** The coach's instructions or intentions. Describe the change; don't invent the reason.

## Progressive and line-breaking passes

**What it is.** A progressive pass moves the ball substantially closer to the opponent's goal. A line-breaking pass goes through or past a line of opponents, taking several of them out of the game at once. They're how good midfielders and defenders create chances without touching the final ball.

**In our data.** Today: for one pass, how much it gained and how rare that is in this match (`get_pass_rarity`); through balls are marked in the events. The stats engine also counts progressive passes per team.

**Say it.**
- Beginner: "That one pass got them from the middle of the pitch right up to the goal area."
- Fan: "What a pass from Arlo: that took four players out of the game."
- Analyst: "Arlo's ball gained 30 metres: only 2% of passes in this match have been that progressive."

**Don't claim.** How many opponents a pass actually bypassed ("took four players out" is fine as colour only if the pass rarity backs a big gain; never as a counted fact). We don't see the defensive lines.

## Crosses and cut-backs

**What it is.** A cross is a ball from a wide area into the box, often in the air. Many crosses are cleared, so a high number of them can mean a team is short of better ideas. A cut-back is a pass from near the goal line back to a teammate arriving at the edge of the six-yard box or penalty spot, usually a much better chance.

**In our data.** Today: crosses per team in the last 15 minutes and how many led to a shot (`get_patterns`; claimed with at least 7 crosses and at most 1 shot).

**Say it.**
- Beginner: "They keep lifting the ball into the box, but the defenders are heading it away."
- Fan: "Twelve crosses, one shot from them: Northbridge need another way through."
- Analyst: "Cross-heavy and not working: twelve crosses, one shot, and the xG from them is tiny."

**Don't claim.** Aerial battles you didn't see, or that "nobody was attacking the near post".

## Set pieces

**What it is.** Corners, free kicks, throw-ins and penalties restart play from a fixed spot, so teams rehearse them. A large share of goals come from set pieces, and a tall team can get many of its chances this way. Penalties are scored roughly three times out of four.

**In our data.** Today: which recent and key chances came from a corner, free kick or penalty, and a penalty's xG (0.76); no set-piece totals yet. #48: "set-piece threat": shots from set pieces per team.

**Say it.**
- Beginner: "A corner: the ball is kicked in from the corner, and tall players try to head it in."
- Fan: "That's the third chance from a corner for Westvale. Their set pieces are a real threat."
- Analyst: "Westvale's set-piece xG is 0.6 already: more than half their total from dead balls."

**Don't claim.** Specific routines, blocks or decoy runs. We see the delivery and the outcome, not the movement.

## Defending deep (the low block)

**What it is.** A team defends close to its own goal with two compact lines, giving away possession and space far from goal but very little near it. Common when protecting a lead, playing with ten men, or against a stronger side. It invites crosses and long shots, which are usually low-quality chances.

**In our data.** Today, indirectly: possession, shots and xG (the match picture) together with the score and minute, e.g. a team leading late with little of the ball; no shot-distance or cross totals yet. #48: field tilt.

**Say it.**
- Beginner: "Westvale are leading, so they're sitting back and keeping everyone near their own goal."
- Fan: "Westvale have dropped deep to protect the lead, and Northbridge are only getting long shots."
- Analyst: "Westvale are in a low block: Northbridge have 70% of the ball late on, but their shots average under 0.05 xG."

**Don't claim.** The exact shape ("a back five") or distances between lines.

## Game state and the late game

**What it is.** The score and the clock change how teams play. A team chasing the game takes more risks, adds attackers and leaves space behind; a team protecting a lead slows things down, makes defensive substitutions and runs the clock. Late goals matter more, and the ranker already scores them higher.

**In our data.** Today: score, minute, the ranker's reasons ("late equalizer", "against the run of play"), substitutions (who came on and went off), momentum over the last 10 minutes.

**Say it.**
- Beginner: "They're losing with ten minutes left, so they're throwing more players forward to score."
- Fan: "Two attackers on for defenders: Northbridge are going for it."
- Analyst: "All-in from Northbridge: two forwards on, and 75% of the ball since the 80th minute."

**Don't claim.** A player's position on the pitch from a substitution alone ("he's playing as a second striker"). Say who came on, not where they stand.

## Chance quality and expected goals

**What it is.** Not all shots are equal. Expected goals (xG) estimates how often a shot like this one is scored, from where it was taken, the angle, the body part and the pressure. A penalty is about 0.76; a header from a corner is often under 0.1. Over a match, xG shows who created the better chances, which the score alone can hide.

**In our data.** Today: xG for every shot (`get_shot_quality` with a label: big chance, half chance, low-probability effort), totals per team, and the labels the ranker uses.

**Say it.**
- Beginner: "A great chance: from there, players score more often than not." (no "xG")
- Fan: "That was a 35% chance. He should have scored."
- Analyst: "0.35 xG and off target. Northbridge's xG is 1.6 now, with nothing to show for it."

**Don't claim.** "Unlucky" or "great save" unless the outcome supports it: a saved shot is a save, but we don't see how good it was. Never contradict the label from `get_shot_quality`.

## Playing with ten men

**What it is.** After a red card a team plays the rest of the match one player short and cannot replace them. Usually it drops deeper, attacks with fewer players and relies on counters and set pieces; the team with eleven gets more of the ball. A red card early in the match is a much bigger blow than a late one.

**In our data.** Today: the card on the foul (`Red Card` / `Second Yellow`), the minute, and how possession and momentum change after it.

**Say it.**
- Beginner: "One of their players was sent off, so they play the rest of the game with ten instead of eleven."
- Fan: "Down to ten before half-time: Northbridge have a long 50 minutes ahead."
- Analyst: "Since the red: Westvale 68% of the ball and four shots to one. Northbridge have retreated."

**Don't claim.** That the red card was right or wrong. Explain the rule if asked.

---

## Rules worth explaining well

The Q&A agent's short glossary lives in `backend/app/agents/qa.py`. These are the details viewers ask about most, in our words:

- **Offside.** A player is in an offside position if any part of the head, body or feet is in the opponent's half and nearer the goal line than both the ball and the second-last defender (usually the last outfield defender, with the goalkeeper as the last). **Level counts as onside.** Being in that position is not an offence by itself: it's only penalised if, when a teammate plays the ball, the player becomes involved (plays the ball, blocks the goalkeeper's view, or gains an advantage). There's **no offside from a throw-in, a goal kick or a corner**. The other team gets an indirect free kick.
- **Penalty.** A direct free-kick foul (a trip, push, hold, or a deliberate handball) by a defender inside their own penalty area. One shot from the penalty mark, 11 metres out, with only the goalkeeper to beat; everyone else waits outside the area until it's kicked.
- **Handball.** It's an offence to deliberately handle the ball, or to make the body unnaturally bigger with the arm. Not every touch on the hand is a foul. We can't judge which it was: we don't see the arm.
- **Yellow and red cards.** A yellow is a caution (a reckless foul, stopping a promising attack, time-wasting, dissent). Two yellows in one match make a red. A straight red is for serious foul play, violent conduct, or denying an obvious goal-scoring opportunity.
- **Advantage.** The referee can let play continue after a foul if stopping it would hurt the fouled team. A card can still be given at the next stoppage.
- **Stoppage time.** Time lost to substitutions, injuries, goals and delays is added at the end of each half; the fourth official shows the minimum.

## Further reading

Sources we learned from, to read rather than copy:

- The IFAB *Laws of the Game*, the official rules of football: [theifab.com](https://www.theifab.com/laws/). The rules above are explained in our own words; the Laws' text belongs to the IFAB.
- Wikipedia's articles on football tactics and formations (CC BY-SA 4.0): background only, nothing pasted.
- Public writing on football analytics concepts such as expected goals, PPDA, field tilt and expected threat. We implement our own versions; nothing in this project is computed from real match data (see [DATA_POLICY.md](../DATA_POLICY.md)).
