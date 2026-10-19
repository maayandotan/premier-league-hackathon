# Data policy

Rules for how this project uses data. Everyone working on the repo follows them.

The hackathon [Official Rules](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md) require synthetic data, and everything we submit is licensed to Microsoft and the Premier League. This repo will be public. Real data has its own license terms.

## The rules

1. **Event format.** Our event schema mirrors [StatsBomb's open event format](https://github.com/statsbomb/open-data) (JSON, 120×80 pitch). Every data source goes through an adapter into our internal event model.

2. **Real data is for testing code locally, nothing more.** StatsBomb Open Data may be used on your own machine to develop and debug our code (adapter, replay, stats engine, agents). Read the [StatsBomb Public Data User Agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf) and register on their [resource centre](https://www.statsbomb.com/resource-centre) before using it. Their agreement forbids commercial use of the data **or any analysis derived from it**, and requires their logo on published analysis, so nothing derived from it goes into the submission.

3. **Real data never enters the repo.** Fetch it at runtime with `statsbombpy`, or store it under `data/real/`, which is git-ignored. Don't paste real events into code, tests, fixtures or docs.

4. **Nothing real in the submission or the demo.** No real player names, club names, logos or real match data in the code, README, screenshots or demo video. All teams and players are fictional.

5. **Nothing in the submission is derived from real data.** The synthetic generator is tuned with general football knowledge (e.g. ~25 shots and ~2.7 goals per match), not with numbers computed from StatsBomb data. Models we submit (e.g. xG) are trained on synthetic data only. No comparisons or validation results against real data in the README, docs or video.

6. **Third-party assets need a compatible license and credit.** Sounds, images or fonts must be CC0, CC BY or similar (anyone may use them, commercially too). Record the source and license in a `CREDITS.md` next to the files, and credit them in the README and the video description. No music or recordings without a clear license.

7. **No secrets in the repo.** API keys and connection strings go in `.env`, which is git-ignored. Never share keys in chat groups.

## Folder layout

| Path | What goes there | In git? |
|---|---|---|
| `data/real/` | Real open data for local testing | No |
| `data/synthetic/` | Generated matches | Yes |
| `.env` | Keys and secrets | No |

When in doubt, leave it out and ask the team.
