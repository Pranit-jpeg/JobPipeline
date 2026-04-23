"""Loads the user identity profile used by the generation/ tool.

Reads profile.json if present, otherwise falls back to profile.example.json
(so a fresh clone still imports cleanly — the generation tool will produce
placeholder output until the user creates a real profile.json).
"""
import json
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_profile() -> dict:
    for name in ("profile.json", "profile.example.json"):
        path = os.path.join(_ROOT, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("name_upper", data["name"].upper())
            data.setdefault("first_name", data["name"].split()[0])
            data.setdefault("name_slug", data["name"].replace(" ", "_"))
            return data
    raise FileNotFoundError(
        "No profile found. Copy profile.example.json to profile.json and fill in your details."
    )


PROFILE = load_profile()
