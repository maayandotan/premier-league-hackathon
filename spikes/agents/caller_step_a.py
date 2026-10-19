"""Caller, Step A: ONE raw call to the model with a system message. No framework, no libraries.

What to notice:
- The request is just a list of messages: "system" (the agent's job) + "user" (the input).
- The model has no memory: everything it knows about the moment is in this request.
- We sign in with your Azure login (az login), not with a key.

Run from the repo root:  python3 spikes/agents/caller_step_a.py
"""
import json
import subprocess
import time
import urllib.error
import urllib.request

ENDPOINT = "https://foundry-pl-hackathon.cognitiveservices.azure.com"
DEPLOYMENT = "gpt-4.1-mini"
URL = f"{ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version=2024-10-21"

# 1. The agent's "job description". This is the part you'll tune.
SYSTEM = """You are the play-by-play caller in a live football broadcast.
Call what is happening right now, the way it sounds when spoken live:
short bursts, ellipses for build-up, exclamations for big moments.
Maximum 12 words.
Describe, don't explain: the analyst handles the "why".
Use only facts from the input. No adjectives about the quality of a shot,
pass or player (no "stunning", "powerful", "brilliant") unless the input says so."""

# 2. The input: one moment from the match (fictional teams, DATA_POLICY.md).
USER = """Minute 80, score now Northbridge FC 2 - 2 Westvale United.
Event: Shot by M. Ferro (Northbridge FC), left foot, from the edge of the box. Outcome: Goal.
Moment: late equalizer."""


def azure_token() -> str:
    """A short-lived token from your `az login` session."""
    return subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://cognitiveservices.azure.com",
         "--query", "accessToken", "-o", "tsv"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def call_model(messages: list[dict], response_format: dict | None = None,
               temperature: float = 0.9) -> tuple[dict, float]:
    payload = {"messages": messages, "max_tokens": 60, "temperature": temperature}
    if response_format:
        payload["response_format"] = response_format
    body = json.dumps(payload).encode()
    request = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {azure_token()}",
        "Content-Type": "application/json",
    })
    start = time.perf_counter()
    for attempt in range(3):  # network calls fail sometimes: retry twice, quickly
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response), time.perf_counter() - start
        except urllib.error.URLError as error:
            if attempt == 2:
                raise
            print(f"   (network error: {error.reason}, retrying...)")
            time.sleep(0.3 * (attempt + 1))


def main() -> None:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER},
    ]
    print("=== WHAT WE SEND ===")
    print(json.dumps(messages, indent=2))

    for attempt in range(1, 4):  # same request three times: watch it vary
        response, seconds = call_model(messages)
        message = response["choices"][0]["message"]
        usage = response["usage"]
        print(f"\n=== RESPONSE {attempt} ({seconds:.2f}s, {usage['prompt_tokens']} tokens in, "
              f"{usage['completion_tokens']} out) ===")
        print(f"role: {message['role']}")
        print(f"text: {message['content']}  [{len(message['content'].split())} words]")


if __name__ == "__main__":
    main()
