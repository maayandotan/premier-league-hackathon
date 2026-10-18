# Speech spike (issue #3)

Quick tests of Azure AI Speech for the two-voice commentary and the viewer's spoken questions.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install requests python-dotenv numpy
cp .env.example .env   # then paste the key from the Azure portal:
                       # speech-pl-hackathon → Keys and Endpoint → KEY 1
```

## Run

```bash
.venv/bin/python spikes/speech/tts_dialogue.py --lang en     # caller (Guy, US) + analyst (Sonia, UK)
.venv/bin/python spikes/speech/tts_dialogue.py --crowd      # with crowd ambience + goal roar
.venv/bin/python spikes/speech/tts_dialogue.py --flat --name flat   # same lines without excitement, to compare
.venv/bin/python spikes/speech/tts_dialogue.py --lang he     # Hebrew version
.venv/bin/python spikes/speech/tts_dialogue.py --voices "en-US-Andrew:DragonHDLatestNeural,en-US-Ava:DragonHDLatestNeural"
.venv/bin/python spikes/speech/stt_question.py               # spoken question → text
```

Audio is written as WAV to `spikes/speech/out/` (git-ignored).

## Resource

- `speech-pl-hackathon`, free tier (F0), **France Central**
- Our Azure for Students subscription only allows: francecentral, italynorth, austriaeast, switzerlandnorth, israelcentral

## Voices and excitement

- **Default voices:** caller `en-US-GuyNeural` (American), analyst `en-GB-SoniaNeural` (British). Hebrew: Avri / Hila.
- **Excitement levels 0–2 per line**, using the voice's built-in styles: level 1 = `excited`, level 2 = `shouting`. Never speed up the voice; it sounds bad.
- Callers that support `excited` + `shouting`: Guy, Davis, Tony, Jason, Ethan (MAI-Voice-2). Compare with `--voices "<caller>,en-GB-SoniaNeural"`.
- **Build a crescendo:** split a big moment into short caller lines that rise in level ("through ball... in behind..." at 1, then "GOAL!" at 2). The agents should write goal moments this way.

## Crowd sound

- `crowd.py` generates a crowd murmur for the whole match and a roar for goals from shaped noise, so there's no licensing question.
- It's a placeholder: a real royalty-free crowd recording will sound better.
- In the real app the mix happens in the browser (Web Audio): the ambience loops, the roar is triggered on goal events, and the commentary plays on top.
