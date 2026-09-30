"""§4.3 automated Telugu QA: catches a translation that dropped, changed, or
added a number, date, currency amount, URL, or negation relative to the
English source, left a required field empty, or isn't Telugu at all.
Deterministic string/regex comparison, not a model call — a translation is
checked against the text it was derived from, not judged in isolation.

Numbers, dates, currency amounts, and URLs are conventionally kept in
Latin/digit form even inside Telugu script output, so comparing them token
for token is a real signal, not a language mismatch. Numbers are compared
as whole tokens (so "5" never matches inside "50") and as a multiset: the
Telugu must carry exactly the English numbers, no more and no fewer.

This is a floor, not a fidelity check: it can't tell a faithful sentence
from a fluent wrong one with the same numbers. The §4.3 native-speaker
review sample still applies (review 2026-09-29 #5).
"""

from __future__ import annotations

import re
from collections import Counter

# Telugu digits (౦-౯) normalize to ASCII before any comparison.
_TE_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789")
# Whole numeric tokens: not preceded by a digit/decimal point, grouping commas
# allowed (Western "100,000" and Indian "1,00,000" both normalize to 100000).
_NUMBER_RE = re.compile(r"(?<![\d.])\d+(?:,\d+)*(?:\.\d+)?")
_URL_RE = re.compile(r"https?://\S+")
_CURRENCY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?(?![\d])|\d[\d,]*(?:\.\d+)?\s?(?:USD|INR)\b")
_NEGATION_RE = re.compile(r"\b(not|never|no longer|cannot|without|neither|nor|none)\b|n['’]t\b", re.IGNORECASE)
# English that carries a negative sense without a negation word; a Telugu
# rendering of these may legitimately use a negation marker, so it doesn't
# count as an added negation. Explicit words, not prefixes: "un-" would
# excuse "United States", "ban" would excuse "bank".
_NEGATIVE_SENSE_RE = re.compile(
    r"\b(no|nobody|nothing|lack\w*|unable|unless|unlike|unpaid|unauthori[sz]ed|undocumented|unemploy\w*|"
    r"fail\w*|den(y|ied|ies|ial)|refus\w*|reject\w*|missing|missed|absen\w*|block\w*|bans?|banned|halt\w*|"
    r"stop\w*|invalid\w*|illegal\w*|disallow\w*|declin\w*|non-\w+|off|free)\b",
    re.IGNORECASE,
)
# Common Telugu negation markers a faithful translation of an English
# negation would be expected to carry one of.
_TE_NEGATION_MARKERS = ("కాదు", "లేదు", "కాలేదు", "వద్దు", "లేదని", "కాదని", "లేరు", "లేము", "రాదు", "కూడదు", "లేకుండా")
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
_TELUGU_CHAR_RE = re.compile(r"[ఀ-౿]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
# Headlines keep acronyms and names in Latin ("USCIS", "H-1B"), so this only
# asks that Telugu be a real share of the letters, not the majority.
MIN_TELUGU_SCRIPT_SHARE = 0.25
# Review 2026-09-30 R2: models slip Kannada or Hindi words into Telugu. Any
# other Indic-script character fails the field, unless the English carries
# that same script (a quoted name or slogan). The dandas U+0964/U+0965 are
# shared punctuation, so they sit outside these ranges.
_OTHER_INDIC_SCRIPT_RES = {
    "DEVANAGARI": re.compile(r"[ऀ-ॣ०-ॿ]"),
    "BENGALI": re.compile(r"[ঀ-৿]"),
    "GURMUKHI": re.compile(r"[਀-੿]"),
    "GUJARATI": re.compile(r"[઀-૿]"),
    "ODIA": re.compile(r"[଀-୿]"),
    "TAMIL": re.compile(r"[஀-௿]"),
    "KANNADA": re.compile(r"[ಀ-೿]"),
    "MALAYALAM": re.compile(r"[ഀ-ൿ]"),
}


def _normalize_number(match: str) -> str:
    return match.replace(",", "")


def _numbers(text: str) -> Counter[str]:
    return Counter(_normalize_number(m) for m in _NUMBER_RE.findall(text.translate(_TE_DIGITS)))


def _currencies(text: str) -> Counter[str]:
    return Counter(re.sub(r"[\s,]", "", m) for m in _CURRENCY_RE.findall(text.translate(_TE_DIGITS)))


def find_qa_issues(en_text: str, te_text: str) -> list[str]:
    """Compares one English field with its Telugu rendering. Returns a list
    of issue codes; empty means the field passes QA."""
    issues: list[str] = []

    en_numbers, te_numbers = _numbers(en_text), _numbers(te_text)
    for number in sorted((en_numbers - te_numbers).elements()):
        issues.append(f"MISSING_NUMBER:{number}")
    for number in sorted((te_numbers - en_numbers).elements()):
        issues.append(f"UNEXPECTED_NUMBER:{number}")

    for match in _URL_RE.findall(en_text):
        if match not in te_text:
            issues.append(f"MISSING_URL:{match}")

    for currency in sorted((_currencies(en_text) - _currencies(te_text)).elements()):
        issues.append(f"MISSING_CURRENCY:{currency}")

    for match in _MONTH_RE.findall(en_text):
        te_month = _MONTH_TE.get(match.lower())
        if match not in te_text and (te_month is None or te_month not in te_text):
            issues.append(f"MISSING_DATE:{match}")

    te_negated = any(marker in te_text for marker in _TE_NEGATION_MARKERS)
    if _NEGATION_RE.search(en_text):
        if not te_negated:
            issues.append("MISSING_NEGATION")
    elif te_negated and not _NEGATIVE_SENSE_RE.search(en_text):
        # "approved" rendered as "not approved": a reversed fact.
        issues.append("UNEXPECTED_NEGATION")

    return issues


def _script_issue(field: str, te_text: str) -> str | None:
    telugu = len(_TELUGU_CHAR_RE.findall(te_text))
    latin = len(_LATIN_LETTER_RE.findall(te_text))
    if telugu == 0 or telugu / (telugu + latin) < MIN_TELUGU_SCRIPT_SHARE:
        return f"NOT_TELUGU_SCRIPT:{field}"
    return None


def _mixed_script_issue(field: str, en_text: str, te_text: str) -> str | None:
    for script_re in _OTHER_INDIC_SCRIPT_RES.values():
        if script_re.search(te_text) and not script_re.search(en_text):
            return f"MIXED_SCRIPT:{field}"
    return None


def find_variant_qa_issues(
    en: tuple[str, str, str | None], te: tuple[str | None, str | None, str | None]
) -> list[str]:
    """QA for a whole Telugu variant, as (headline, summary, why_matters)
    against the English one. Headline and summary are always required; the
    why-matters line is required whenever the English has one."""
    issues: list[str] = []
    for field, en_text, te_text in zip(("headline", "summary", "why_matters"), en, te, strict=True):
        en_text = (en_text or "").strip()
        te_text = (te_text or "").strip()
        if not te_text:
            if en_text or field != "why_matters":
                issues.append(f"MISSING_FIELD:{field}")
            continue
        issues += find_qa_issues(en_text, te_text)
        if script_issue := _script_issue(field, te_text):
            issues.append(script_issue)
        if mixed_issue := _mixed_script_issue(field, en_text, te_text):
            issues.append(mixed_issue)
    return issues
