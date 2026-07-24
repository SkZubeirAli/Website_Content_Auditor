"""Load and validate the searchable word/phrase list from a JSON file.

The word list file lives at config/words.json by default and can be freely
edited (add/remove entries) without touching any program code. Each entry
looks like:

    {"word": "Expert", "replacements": ["capable team", "dedicated team"]}
"""
import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "words.json"


def load_word_list(path=None):
    """Load and lightly validate the word list.

    Returns a list of dicts: [{"word": str, "replacements": [str, ...]}, ...]
    """
    path = Path(path) if path else DEFAULT_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Word list file must contain a JSON array of objects.")

    cleaned = []
    for entry in data:
        word = str(entry.get("word", "")).strip()
        replacements = entry.get("replacements", [])
        if not word:
            continue
        if isinstance(replacements, str):
            replacements = [replacements]
        cleaned.append({"word": word, "replacements": [str(r) for r in replacements]})

    if not cleaned:
        raise ValueError("Word list is empty after validation.")

    return cleaned


def save_word_list(word_list, path=None):
    """Persist a word list back to disk (used by future 'edit word list' UI)."""
    path = Path(path) if path else DEFAULT_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(word_list, f, indent=2, ensure_ascii=False)
    return path
