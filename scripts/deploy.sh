#!/usr/bin/env bash
# Build the app image and roll it out to Azure Container Apps (#24). See docs/deploy.md.
#
#   scripts/deploy.sh            # build, push and deploy a new version
#
# Needs: Docker running, `az login` as the subscription owner, and the resources in docs/deploy.md.
# The image never contains data/real or .env (see .dockerignore and DATA_POLICY.md).
set -euo pipefail

REGISTRY=acrplhackathon
APP=match-intelligence
GROUP=rg-pl-hackathon
TAG="v$(date +%Y%m%d-%H%M%S)"
IMAGE="$REGISTRY.azurecr.io/$APP:$TAG"

cd "$(dirname "$0")/.."

# Student subscriptions can't build in Azure (ACR Tasks), so we build locally for linux/amd64.
az acr login -n "$REGISTRY" >/dev/null
docker buildx build --platform linux/amd64 -t "$IMAGE" --push .

az containerapp update -n "$APP" -g "$GROUP" --image "$IMAGE" -o none
URL="https://$(az containerapp show -n "$APP" -g "$GROUP" --query properties.configuration.ingress.fqdn -o tsv)"
echo "Deployed $TAG -> $URL"
curl -fsS "$URL/health" && echo
