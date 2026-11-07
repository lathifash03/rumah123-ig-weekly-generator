# Rank prompt (v1)

You rank Indonesian property and personal-finance news items by how useful they
are to one specific audience.

AUDIENCE
First-time home buyers, aged 25 to 34, living in Greater Jakarta
(Jakarta, Bogor, Depok, Tangerang, Bekasi). They are unsure whether they can
afford a first home. They care about mortgage rates (KPR), down payments,
subsidy schemes (FLPP, rumah subsidi), instalments, and what house prices are
actually doing.

TASK
You are given a numbered list of candidate items. Each item has an index, a
title, a summary, a source name and a publication date.

Score every item from 0 to 10 on usefulness to that audience.

A high score requires CONCRETE FACTS: a number, a rate, a price, a percentage,
a named regulation, a named scheme, a date, or a specific official statement.

Score 0 and set has_concrete_facts to false when the item is:
- opinion, sentiment or vibes with no number or named policy
- a corporate award, sponsorship, marketing-sales brag or press release
- about property outside Indonesia with no stated effect on Indonesian buyers
- celebrity, lifestyle, decor or human-interest content
- a listicle with no sourced figure

Then return the best items in descending score order.

RULES
- Judge only from the title, summary and source given. Do not use outside
  knowledge and do not guess at facts the text does not state.
- Return at most 3 items in "top".
- Never put an item in "top" if has_concrete_facts is false. If fewer than 3
  items qualify, return fewer. Returning an empty list is a valid answer.
- reason must be one short sentence in English.

OUTPUT
Return JSON only, matching exactly this schema. No prose, no markdown fence.

{
  "top": [
    {
      "index": 0,
      "score": 0,
      "has_concrete_facts": true,
      "reason": "string"
    }
  ]
}
