"""Tests never call Azure: commentary falls back to templates, and there's no audio."""
import os

os.environ["USE_AGENTS"] = "false"
os.environ["USE_SPEECH"] = "false"
