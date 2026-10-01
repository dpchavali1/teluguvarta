"""Review 2026-09-30 R9: the brevity rules from `docs/EDITORIAL_STYLE.md`,
as the prompt text the generation, translation and why-matters calls share.

Guidance only. Publication rules stay in `app/content/publication.py`
(ADR-026); none of these lengths blocks a story.
"""

from __future__ import annotations

GENERATION_STYLE = (
    "Style: the headline states the news in at most 12 words, one clause, no "
    "colon or second clause. The summary is two or three sentences (about 40 to "
    "80 words): lead with what happened, then the most useful concrete detail "
    "the evidence gives (who, what, when, how many). No commentary or filler. "
    "'Why this matters' is one sentence (at most 30 words) naming a concrete "
    "consequence for readers that the evidence supports, such as a deadline, an "
    "eligibility or cost change, or who is affected. If the evidence supports no "
    "such consequence, return an empty string for why_matters_en; never restate "
    "the headline or say that something 'raises questions' or 'creates tension'. "
    "Never invent dates, actions, numbers or local impact. "
)

TRANSLATION_STYLE = (
    "Write the headline as a short Telugu news headline, not a full sentence, "
    "with the same meaning and nothing added. Keep the summary and why_matters "
    "as concise as the English. If the English why_matters is empty, return an "
    "empty why_matters_te. "
)

WHY_MATTERS_STYLE = (
    "Use one sentence of at most 30 words naming a concrete consequence that "
    "the story text supports (a deadline, an eligibility or cost change, who is "
    "affected). Never invent dates, actions, numbers or local impact. If the "
    "story gives no specific consequence for this reader, return an empty "
    "string for why_matters. "
)
