"""P07 / ADR-049: turn text copied from the official bulletin PDF into draft entries.

Pure (no DB, no network). The editor still compares the draft with the official
notice and approves it; a count mismatch is reported instead of guessed."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from app.content.visa_bulletin import COUNTRIES

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_VALUE = re.compile(r"^(?:\d{2}[A-Z]{3}\d{2}|C|U)$")
_MONTH_HEADING = re.compile(r"Immigrant Numbers for ([A-Za-z]+) (\d{4})")
_SECTIONS = (
    ("FINAL_ACTION", r"A\.\s*Final Action Dates for Family-Sponsored", ("F1", "F2A", "F2B", "F3", "F4")),
    ("DATES_FOR_FILING", r"B\.\s*Dates for Filing Family-Sponsored", ("F1", "F2A", "F2B", "F3", "F4")),
    ("FINAL_ACTION", r"A\.\s*Final Action Dates for Employment-Based", ("EB1", "EB2", "EB3", "EB3-OW", "EB4", "EB5")),
    ("DATES_FOR_FILING", r"B\.\s*Dates for Filing of Employment-Based", ("EB1", "EB2", "EB3", "EB3-OW", "EB4", "EB5")),
)
_LABELS = {
    ("F1",): "F1", ("F2A",): "F2A", ("F2B",): "F2B", ("F3",): "F3", ("F4",): "F4",
    ("1st",): "EB1", ("2nd",): "EB2", ("3rd",): "EB3", ("Other", "Workers"): "EB3-OW",
    ("4th",): "EB4", ("5th", "Unreserved"): "EB5",
}
_END = re.compile(r"\n\s*(?:B\.\s*Availability|C\.\s*Extension|D\.\s*U\.S\.)|\n\s*[5-9]\.\s+Section")


@dataclass
class ParsedBulletin:
    month: str | None = None
    entries: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


MAX_PDF_BYTES = 5_000_000
MAX_PDF_PAGES = 30


def text_from_pdf(data: bytes) -> str:
    """Extract text from an uploaded bulletin PDF; ValueError on anything unreadable."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF is too large")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("PDF is encrypted or too long")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PyPdfError, OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Could not read the PDF") from exc


def _cutoff(token: str) -> str:
    if token in ("C", "U"):
        return token
    month = _MONTHS.index(token[2:5]) + 1
    return f"{2000 + int(token[5:])}-{month:02d}-{int(token[:2]):02d}"


def _month(text: str) -> str | None:
    found = _MONTH_HEADING.search(text)
    if not found or found.group(1)[:3].upper() not in _MONTHS:
        return None
    return f"{found.group(2)}-{_MONTHS.index(found.group(1)[:3].upper()) + 1:02d}"


def _rows(section: str, expected: tuple[str, ...]) -> dict[str, list[str]]:
    tokens = section.split()
    rows: dict[str, list[str]] = {}
    for i in range(len(tokens)):
        for words, category in _LABELS.items():
            if category not in expected or category in rows or tuple(tokens[i : i + len(words)]) != words:
                continue
            values = [t for t in tokens[i + len(words) : i + len(words) + 14] if _VALUE.match(t)][: len(COUNTRIES)]
            if len(values) == len(COUNTRIES):
                rows[category] = values
    return rows


def parse_bulletin_text(text: str) -> ParsedBulletin:
    out = ParsedBulletin(month=_month(text))
    if out.month is None:
        out.warnings.append("Could not read the bulletin month (expected 'Immigrant Numbers for <Month> <Year>').")
    for chart, heading, expected in _SECTIONS:
        start = re.search(heading.replace(" ", r"\s+"), text)
        label = f"{chart} {'family' if expected[0] == 'F1' else 'employment'}"
        if not start:
            out.warnings.append(f"Section not found: {label}")
            continue
        rest = text[start.end() :]
        end = _END.search(rest)
        # Family charts end at the next section heading; the end marker only bounds the last chart.
        nxt = re.search(r"\n\s*[A-B]\.\s+(?:Final\s+Action|Dates\s+for\s+Filing)", rest)
        stop = min((m.start() for m in (end, nxt) if m), default=len(rest))
        rows = _rows(rest[:stop], expected)
        for category in expected:
            if category not in rows:
                out.warnings.append(f"Missing row {category} in {label}")
                continue
            for country, token in zip(COUNTRIES, rows[category], strict=True):
                out.entries.append({"chart": chart, "category": category, "country": country, "cutoff": _cutoff(token)})
    return out
