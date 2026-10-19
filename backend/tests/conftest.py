"""Tests never call the real model: commentary falls back to templates."""
import os

os.environ["USE_AGENTS"] = "false"
