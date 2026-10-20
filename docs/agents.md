# Agent design

How our commentary system turns a match event into words in the viewer's ears: which parts are AI agents, which are plain code, how they cooperate, and the order to build them in.

<p align="center"><img src="images/agent-flow.svg" alt="Agent flow: match feed, stats engine, moment ranker, producer, then the caller, analyst and Q&A agents, the fact-checker, voice, and the viewer" width="820"></p>

**5 AI agents, 5 code components.** Anything that must be fast, exact or predictable is code. The AI agents write the words and judge what's worth saying.

## The flow in 6 steps

The numbers match the black badges in the graph.

**① An event arrives.** The match feed delivers events one by one, as a live data provider would: a pass, a shot, a foul. For the hackathon the feed is a replay of a synthetic match.

**② The Stats Engine updates the numbers.** Score, xG, possession, momentum, tempo. This is plain code, so the numbers are always exact. The agents never compute numbers themselves: they ask the Stats Engine.

**③ The Moment Ranker decides how interesting it is.** Every event gets a score from 0 to 10 with a reason: a routine pass is 0, a line-breaking pass 4, a shot 7, a goal 10. Most events score low, which is how the system knows to stay quiet.

**④ The Producer decides who speaks, and when.** It's the conductor. Live action goes to the **Caller**. Quiet moments (a foul, the ball out of play, the seconds after a goal) go to the **Analyst**. A viewer's question goes to **Q&A**. It also cuts lines that are no longer relevant, and lets urgent moments interrupt everything else.

**⑤ The Fact-Checker verifies every number.** Before anything the Analyst or Q&A says is spoken, each number in it is checked against the Stats Engine. A wrong number means the line is dropped or rewritten. The Caller skips this step: it describes and doesn't quote numbers, and it has to be fast.

**⑥ Voice speaks it.** The line becomes speech (Guy calls, Sonia analyses), mixed over the crowd, and plays in the viewer's browser.

In the background, the **Viewer Profile** (level, language) and the **Storyteller** (the match story so far) feed every AI agent, so the commentary fits the viewer and has memory.

## Meet the team

### Code components

**🧮 Stats Engine** ([#10](https://github.com/maayandotan/premier-league-hackathon/issues/10))
*Purpose: be the single source of truth for every number.*
Keeps live match state and computes xG, possession (overall and last 10 minutes), momentum, tempo, pass progression and rarity. Every method is also an **agent tool**, so the Analyst asks "what's the momentum?" and gets an exact answer instead of guessing.

**🎯 Moment Ranker** ([#12](https://github.com/maayandotan/premier-league-hackathon/issues/12))
*Purpose: separate the moments worth talking about from the noise.*
A real match has about 3,000 events, and commentary needs a few hundred lines. The ranker scores each event 0–10 with a reason ("late equalizer", "line-breaking pass"), using simple rules and context like the minute, the score and momentum.

**🎬 Producer** ([#16](https://github.com/maayandotan/premier-league-hackathon/issues/16))
*Purpose: keep the broadcast coherent, like a TV director.*
A priority queue with rules. It decides which agent to ask, when the Analyst gets airtime, which lines have expired, and when a goal interrupts everything. The agents never talk to each other directly; everything goes through the Producer, which keeps timing in one place.

**👤 Viewer Profile** ([#15](https://github.com/maayandotan/premier-league-hackathon/issues/15))
*Purpose: make the same match feel different for each viewer.*
Stores the viewer's level (beginner, fan, analyst), language, and which concepts were already explained, so a beginner gets offside explained once, not every time.

**🔊 Voice** ([#19](https://github.com/maayandotan/premier-league-hackathon/issues/19), [#20](https://github.com/maayandotan/premier-league-hackathon/issues/20))
*Purpose: turn text into a broadcast.*
Azure Speech with two voices (Guy for the Caller, excited on big moments; Sonia for the Analyst), the crowd bed and the goal roar, and a playback queue that can cut a line mid-sentence when something urgent happens.

### AI agents (Microsoft Foundry, gpt-4.1-mini)

**🎙️ Caller** ([#13](https://github.com/maayandotan/premier-league-hackathon/issues/13))
*Purpose: tell the viewer what's happening, right now.*
Short, punchy play-by-play: "Arlo, through ball, Ferro is in behind... GOAL!" Builds big moments as a crescendo of short lines. It has no tools and must answer in under a second, because it has to keep up with play. It describes; it never explains.

**🧠 Analyst** ([#14](https://github.com/maayandotan/premier-league-hackathon/issues/14))
*Purpose: explain why a moment mattered, at the viewer's level.*
The heart of the product. In quiet moments it calls the Stats Engine's tools and explains: "That came against the run of play: Westvale had 68% of the ball, and the shot was only a 9% chance." A beginner hears a simpler version, an analyst a more technical one.

**✅ Fact-Checker** ([#17](https://github.com/maayandotan/premier-league-hackathon/issues/17))
*Purpose: guarantee the commentary never makes up a number.*
Checks every number the Analyst and Q&A say against the tool results they actually got. Mostly code, so it's instant; a small model only steps in when a claim is ambiguous. Rejections are logged, so we can show the judges "0 made-up numbers".

**❓ Q&A** ([#18](https://github.com/maayandotan/premier-league-hackathon/issues/18))
*Purpose: answer the viewer's questions without stopping the match.*
"Why was that a foul?" It looks at the events **just before** the question was asked (so it knows which foul), checks the rules glossary and the stats, and answers in 2–3 sentences at the viewer's level, in the Analyst's voice.

**📖 Storyteller** ([#30](https://github.com/maayandotan/premier-league-hackathon/issues/30))
*Purpose: give the commentary memory, and write the recaps.*
Every ~5 minutes it updates a short "story so far" that the Analyst and Q&A read, so they can refer back ("after dominating the first half...") and don't repeat themselves. At half-time and full-time it writes a recap, personalized by level.

## Who talks when

The Producer gives every line a priority and an expiry:

| What | Priority | Expires after | Who speaks |
|---|---|---|---|
| Goal, red card, penalty | 🔴 urgent | never | Caller (crescendo), then Analyst |
| Viewer question | 🔵 high | — | Q&A, in the Analyst's voice |
| Big chance, important foul | 🟠 high | 10 s | Caller |
| Analyst insight | 🟡 medium | 20 s | Analyst |
| Background stat | ⚪ low | 30 s | Analyst |
| Half-time / full-time recap | 🟣 at the break | — | Storyteller, both voices |

- **Urgent** cuts whatever is playing and clears lower-priority lines.
- **Expired lines are dropped**, never played late.
- **The match never pauses** for a question; only urgent events interrupt an answer.

## One goal, start to finish

| Step | What happens |
|---|---|
| ① | Feed: Pass (through ball) → Carry → Shot (Goal) |
| ② | Stats Engine: score 1–0, xG of the shot 0.09, momentum still with Westvale |
| ③ | Ranker: pass 4 "line-breaking", carry 6 "into the box", shot 10 "goal against the run of play" |
| ④ | Producer: the build-up goes to the Caller at excitement 1; the goal is urgent, so excitement 2 and the crowd roar |
| | Caller: "Arlo, through ball, Ferro is in behind..." → "GOAL! Northbridge lead!" |
| ④ | Producer: the restart is a quiet moment, so it asks the Analyst about the goal |
| | Analyst calls `get_momentum`, `get_shot_quality`, `get_pass_rarity`, then: "That came against the run of play: Westvale had 68% of the ball, and the shot was only a 9% chance." |
| ⑤ | Fact-Checker: 68% ✓, 9% ✓ |
| ⑥ | Voice: Sonia reads it, the crowd still buzzing underneath |

## Agent contracts

Every AI agent gets the **viewer profile** and returns JSON, never free text.

| Agent | Triggered by | Input | Tools | Output | Time budget |
|---|---|---|---|---|---|
| 🎙️ Caller | Producer, live events scored ≥ 3 | event, score, clock, last 3 events | none | `speaker, excitement 0–2, text` (1 short sentence) | < 1 s |
| 🧠 Analyst | Producer, quiet moments | topic event(s), story so far | `get_score`, `get_possession`, `get_momentum`, `get_tempo`, `get_shot_quality`, `get_pass_rarity`, `get_recent_events`; later `explain_shot` (SHAP, #11) | `text` + `claims` (each number and the tool it came from), 1–3 sentences | 2–4 s |
| ✅ Fact-Checker | every Analyst / Q&A line | the line, its claims, the tool results | — | `pass` or `fail` + reason | ~0 s (code path) |
| ❓ Q&A | the viewer | question, match time it was asked, story so far | `get_events_before(time)`, stats tools, `get_rule(topic)` | 2–3 sentences | 2–3 s |
| 📖 Storyteller | every ~5 min, half-time, full-time | stats snapshot, key moments, previous story | — | `story`, `recap` | background |

## How it runs

- **The Producer and the pipeline are Python code** in `backend/app/agents/`, on asyncio. Real-time priorities and interruptions don't belong inside a language model.
- **The AI agents run on Microsoft Foundry** with `gpt-4.1-mini`. The stats tools are Python functions. Foundry Agent Service vs Microsoft Agent Framework is decided in #2.
- **Agents never call each other.** Everything goes through the Producer: easier to debug, and easy to show the judges.

## Build order

Each step ends with something that works and can be shown.

| Step | Build | Result | Issues |
|---|---|---|---|
| **1** | Moment Ranker + **Caller** + a simple Producer ("call everything scored ≥ 3") | Live play-by-play as text | #12, #13 |
| **2** | **Analyst** with stats tools + Producer quiet moments + viewer level | Caller and Analyst in dialogue, adapted to the level | #14, #16, #15 |
| **3** | **Fact-Checker** + Voice | Two voices, verified numbers | #17, #19, #20 |
| **4** | **Q&A** + push-to-talk | Questions mid-match | #18, #21 |
| **5** | **Storyteller** + recaps | Memory and recaps | #30 |

Steps 1–2 are the basic tier: with them alone we have a submission. Steps 3–4 make it strong; 5 is polish.

**Working in parallel:** the Caller only needs the Ranker, so it can start as soon as #2 settles the framework. The Analyst needs the stats tools, which are ready in #28.

## Decisions

- [x] Agent framework: **Microsoft Agent Framework** on Foundry (#2): agents are created in code, tools are Python functions, structured output with Pydantic.
- [x] Caller: the model for every moment worth a line (score ≥ 3), with a 2 s deadline and an instant template as the fallback, so the broadcast never waits.
