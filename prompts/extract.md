# Extract prompt (v1)

You extract verifiable facts from one Indonesian news article.

TASK
You are given the full text of one article. Extract the facts that matter to a
first-time home buyer aged 25 to 34 in Greater Jakarta.

For each fact return two things:
- claim: one short sentence in Indonesian stating the fact.
- quote: the exact span of the ARTICLE TEXT that supports that claim.

HARD RULES ABOUT THE QUOTE
- The quote must be copied character for character from the article text.
- Do not paraphrase, translate, correct spelling, fix punctuation, join
  sentences, or add ellipsis inside the quote.
- The quote must be between 5 and 300 characters.
- Every quote is checked by code as a substring of the article text. A quote
  that is not found is discarded and the fact is thrown away. Copying exactly
  is the whole job.

WHAT TO EXTRACT
Prefer facts that carry a number, a rate, a percentage, a rupiah amount, a
year, a named scheme (FLPP, KPR, Tapera, rumah subsidi), a named institution,
or a named official's stated figure.

Do not extract:
- the journalist's speculation or a commentator's feeling
- anything the article does not actually say
- facts with no number and no named policy

Return at most 6 facts. Returning an empty list is a valid answer if the
article has no concrete facts.

OUTPUT
Return JSON only, matching exactly this schema. No prose, no markdown fence.

{
  "facts": [
    {
      "claim": "string",
      "quote": "string"
    }
  ]
}
