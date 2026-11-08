"""Loads the JSON config files. Every calculation constant lives in these files."""
import json
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load(name: str):
    """Load `<name>.json` from the config folder (cached)."""
    with open(CONFIG_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def strip_notes(obj):
    """Remove documentation keys (starting with '_') for API responses."""
    if isinstance(obj, dict):
        return {k: strip_notes(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_notes(v) for v in obj]
    return obj
