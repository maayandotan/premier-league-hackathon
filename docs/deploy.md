# Deployment

**Live:** https://your-call.purplesand-eefdeaf2.francecentral.azurecontainerapps.io

The app's first link, https://match-intelligence-live.purplesand-eefdeaf2.francecentral.azurecontainerapps.io, still works: the old app `match-intelligence-live` runs the same image
(deploy.sh updates both) and sleeps when unused, so it costs nothing while idle and takes a few seconds
to wake.

One container serves everything: the built React site, the API, the live match WebSocket and the crowd audio.

```
browser ──► Azure Container App "your-call" (francecentral)
              ├─ website (frontend/dist, built into the image)
              ├─ FastAPI: /health, /ws/match, /static/audio
              └─ calls ─► Foundry gpt-4.1-mini (managed identity) + Azure Speech (key as secret)
```

## Resources (all in `rg-pl-hackathon`, francecentral)

| Resource | Name | Notes |
|---|---|---|
| Container Registry | `acrplhackathon` (Basic) | ~$0.17/day. The app pulls with its managed identity (AcrPull) |
| Container Apps environment | `cae-pl-hackathon-wp` | **Workload profiles** mode, Consumption profile, no paid log workspace |
| Container App | `your-call` | 0.5 vCPU / 1 GiB, 1 replica always warm, system-assigned identity |
| Container App | `match-intelligence-live` | The app's first name (Azure apps can't be renamed). Same image, min 0 replicas |
| Role assignments | each app's identity → `foundry-pl-hackathon`, `acrplhackathon` | Cognitive Services User, Azure AI Developer; AcrPull |

Settings (environment variables): `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL_DEPLOYMENT`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_KEY` (from the `speech-key` secret), **`ALLOW_REAL_DATA=false`**.

## Data policy in production

- The image never contains `data/real/` or `.env` (`.dockerignore`), checked by listing the image
- `ALLOW_REAL_DATA=false`: `?source=statsbomb:...` is refused on the live site
- Only `demo` and `synthetic:<name>` matches can be played

## Deploy a new version

```bash
scripts/deploy.sh
```

It builds the image locally for `linux/amd64` (student subscriptions can't use ACR cloud builds), pushes it with a timestamp tag, updates both apps and checks `/health`.

## Scaling and cost

- **For judging (Oct 27 – Nov 10):** `your-call` keeps one replica warm so judges never wait (≈ $0.39/day). The old `match-intelligence-live` is at `min-replicas 0`.

  ```bash
  az containerapp update -n your-call -g rg-pl-hackathon --min-replicas 1
  az containerapp update -n match-intelligence-live -g rg-pl-hackathon --min-replicas 0
  ```

- After judging, scale back to 0 or delete the resource group.
- Speech is on the free tier (~25 full matches/month). If it runs out, audio stops but text continues; upgrading Speech to S0 fixes it.

## Why "workload profiles" and not the default

`az containerapp env create` now makes an **express** environment by default. Express environments
don't support managed identity: the app could be created, but **every later update was rejected**
("System-assigned managed identity is not supported ... on express environments"). The environment
is created with `--environment-mode WorkloadProfiles` instead (same consumption billing).

## Not done (yet)

- Deploying from GitHub Actions: needs a federated identity (app registration), which the BGU directory may not allow. Deploys are manual with `scripts/deploy.sh` for now.
