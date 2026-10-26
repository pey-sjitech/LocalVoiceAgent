"""Persist conversation history to disk."""
import json, os
from app import settings

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_BASE, settings.HISTORY_FILE)


def load() -> list:
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [m for m in data if m.get("role") in ("user", "assistant")]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(history: list) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    keep = [m for m in history if m.get("role") in ("user", "assistant") and m.get("content")]
    keep = keep[-settings.MAX_HISTORY_MESSAGES:]
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(keep, f, indent=2, ensure_ascii=False)


def clear() -> None:
    if os.path.exists(_PATH):
        os.remove(_PATH)
