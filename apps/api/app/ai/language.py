"""Deterministic language detection (§7.2: "small/cheap model or
deterministic library" — no AI call needed to tell Telugu from English
script, per NON_NEGOTIABLES' "prefer deterministic code over an LLM call").
"""

from __future__ import annotations

_TELUGU_BLOCK = range(0x0C00, 0x0C7F + 1)


def detect_language(text: str) -> str:
    """Returns 'te' if the text contains Telugu-script characters, 'en' if
    it's non-empty and Telugu-free, else 'unknown'."""
    stripped = text.strip()
    if not stripped:
        return "unknown"
    if any(ord(ch) in _TELUGU_BLOCK for ch in stripped):
        return "te"
    return "en"
