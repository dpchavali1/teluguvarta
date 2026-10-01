# Editorial style: brevity

Review 2026-09-30 R9. Applies to AI drafts and editor-written drafts. These are
writing targets, not publication rules: what blocks a story is ADR-026
(`app/content/publication.py`) and the human-review gates. The AI prompts carry
the same text (`apps/api/app/content/editorial.py`); change both together.

## English

- **Headline**: states the news in at most 12 words. One clause; no colon and
  no second clause. Never the source's headline wording (ADR-002).
- **Summary**: two or three sentences, about 40 to 80 words. Lead with what
  happened, then the most useful concrete detail the sources give (who, what,
  when, how many). No commentary or filler.
- **Why it matters**: one sentence, at most 30 words, naming a concrete
  consequence the sources support: a deadline, an eligibility or cost change,
  who is affected. If the sources support none, leave it empty. Don't restate
  the headline, and don't write lines like "this raises questions" or "this
  creates political tension".
- Never invent dates, actions, numbers or local impact to make a card look
  richer.

## Telugu

- **Headline**: a short Telugu news headline, not a full sentence, with the
  same meaning as the English and nothing added.
- **Summary and why it matters**: as concise as the English. No why-matters
  line when the English has none (the translator's output is dropped).

## Display

- Feed cards show compact attribution (publisher domain plus "Read the
  original source"); the full source title is on story detail and in the
  link's accessible name.
- Headlines are not truncated to hide long copy; fix the copy instead.
- Audience-specific why-matters lines follow the same rule. An empty one means
  "nothing specific for this reader", and the story's general line is shown.
