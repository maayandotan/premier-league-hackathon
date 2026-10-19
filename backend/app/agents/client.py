"""One shared connection to our Foundry project, used by every agent.

Signs in with DefaultAzureCredential: your `az login` locally, the app's managed identity
on Azure. No keys anywhere.
"""
from functools import lru_cache

from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from app.config import settings


def agents_enabled() -> bool:
    configured = bool(settings.foundry_project_endpoint and settings.foundry_model_deployment)
    return settings.use_agents and configured


@lru_cache
def chat_client() -> FoundryChatClient:
    return FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_deployment,
        credential=DefaultAzureCredential(),
    )
