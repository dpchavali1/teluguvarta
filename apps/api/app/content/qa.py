"""§4.3 automated Telugu QA: catches a translation that silently dropped a
number, date, currency amount, URL, or negation present in the English
source. Deterministic string/regex comparison, not a model call — a
translation is checked against the text it was derived from, not judged in
isolation.

Numbers, dates, currency amounts, and URLs are conventionally kept in
Latin/digit form even inside Telugu script output, so "does this substring
still appear in the Telugu text" is a real signal, not a language mismatch.
"""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_URL_RE = re.compile(r"https?://\S+")
_CURRENCY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:USD|INR)")
_NEGATION_RE = re.compile(r"\b(not|n't|never|no longer)\b", re.IGNORECASE)
# Common Telugu negation markers a faithful translation of an English
# negation would be expected to carry one of.
_TE_NEGATION_MARKERS = ("కాదు", "లేదు", "కాలేదు", "వద్దు")
# A dropped month name wouldn't be caught by the number check alone (e.g.
# "March 5" -> "5" surviving isn't enough to prove the date wasn't garbled).
# Unlike numbers/URLs/currency, a real Telugu translation transliterates the
# month name rather than keeping it in Latin script, so the check accepts
# either the canonical Telugu month word or the untranslated English one.
_MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    re.IGNORECASE,
)
_MONTH_TE = {
    "january": "జనవరి", "february": "ఫిబ్రవరి", "march": "మార్చి", "april": "ఏప్రిల్",
    "may": "మే", "june": "జూన్", "july": "జూలై", "august": "ఆగస్టు",
    "september": "సెప్టెంబర్", "october": "అక్టోబర్", "november": "నవంబర్", "december": "డిసెంబర్",
}


def _normalize_number(match: str) -> str:
    return match.replace(",", "")


def find_qa_issues(en_text: str, te_text: str) -> list[str]:
    """Returns a list of issue codes; empty means the variant passes QA."""
    issues: list[str] = []

    for match in _NUMBER_RE.findall(en_text):
        normalized = _normalize_number(match)
        if normalized not in te_text and match not in te_text:
            issues.append(f"MISSING_NUMBER:{match}")

    for match in _URL_RE.findall(en_text):
        if match not in te_text:
            issues.append(f"MISSING_URL:{match}")

    for match in _CURRENCY_RE.findall(en_text):
        if match not in te_text:
            issues.append(f"MISSING_CURRENCY:{match}")

    for match in _MONTH_RE.findall(en_text):
        te_month = _MONTH_TE.get(match.lower())
        if match not in te_text and (te_month is None or te_month not in te_text):
            issues.append(f"MISSING_DATE:{match}")

    if _NEGATION_RE.search(en_text) and not any(marker in te_text for marker in _TE_NEGATION_MARKERS):
        issues.append("MISSING_NEGATION")

    return issues
