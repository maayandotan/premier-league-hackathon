"""Caller, Step D (hello world): the same Caller, now with Microsoft Agent Framework.

Compare with Step A/B: no HTTP, no JSON parsing, no schema dictionary.
- FoundryChatClient: connects to our Foundry project with your `az login`.
- Agent: instructions + options, defined once.
- response_format=CallerLine: the framework asks for that schema and parses the answer for us.

Run from the repo root:  backend/.venv/bin/python spikes/agents/caller_step_d_hello.py
"""
import asyncio
import time

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from pydantic import BaseModel

PROJECT_ENDPOINT = "https://foundry-pl-hackathon.services.ai.azure.com/api/projects/commentary"


class CallerLine(BaseModel):
    text: str


async def main() -> None:
    client = FoundryChatClient(project_endpoint=PROJECT_ENDPOINT, model="gpt-4.1-mini",
                               credential=AzureCliCredential())
    caller = Agent(
        client,
        name="caller",
        instructions="You are the play-by-play caller in a live football broadcast. "
                     "Maximum 12 words, spoken style. Match the EXCITEMENT level (0 calm, 1 building, 2 big).",
        default_options={"temperature": 0.5, "max_tokens": 60, "response_format": CallerLine},
    )
    moment = """minute: 80
score: Northbridge FC 2 - 2 Westvale United
event: Shot
player: M. Ferro
outcome: goal
moment: late equalizer
EXCITEMENT: 2"""
    for attempt in (1, 2):
        start = time.perf_counter()
        response = await caller.run(moment)
        line: CallerLine = response.value  # already a Python object, not text
        print(f"{attempt}: {line.text}   ({time.perf_counter() - start:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
