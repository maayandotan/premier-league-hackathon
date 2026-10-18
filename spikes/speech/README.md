# Speech spike (issue #3)

Quick tests of Azure AI Speech for the two-voice commentary and the viewer's spoken questions.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install requests python-dotenv
cp .env.example .env   # then paste the key from the Azure portal:
                       # speech-pl-hackathon → Keys and Endpoint → KEY 1
```

## Run

```bash
.venv/bin/python spikes/speech/tts_dialogue.py --lang en     # caller + analyst exchange
.venv/bin/python spikes/speech/tts_dialogue.py --lang he     # Hebrew version
.venv/bin/python spikes/speech/tts_dialogue.py --voices "en-US-Andrew:DragonHDLatestNeural,en-US-Ava:DragonHDLatestNeural"
.venv/bin/python spikes/speech/stt_question.py               # spoken question → text
```

Audio is written to `spikes/speech/out/` (git-ignored).

## Resource

- `speech-pl-hackathon`, free tier (F0), **France Central**
- Our Azure for Students subscription only allows: francecentral, italynorth, austriaeast, switzerlandnorth, israelcentral
