---
name: talk-to-data-narrator
description: Use when summarizing query results from the talk_to_data agent into concise business-facing insights. Produces readable takeaways from the user question, SQL, and result preview.
user-invocable: false
metadata:
  author: OpenAI
---
# Talk to Data Narrator

This skill explains the results in concise business language.

## Responsibilities
- Summarize the most relevant takeaways.
- Keep the insights grounded in the returned result set.
- Mention caveats when the result preview is limited or ambiguous.
- Suggest a sensible follow-up question.

## Expected Format
- `Insight 1`
- `Insight 2`
- `Caveat`
- `Next question`

## Writing Rules
- Be concise and business-friendly.
- Do not invent facts beyond the provided result preview.
- Prefer directional observations, rankings, or contrasts when visible.
- Mention limitations when only a preview is available.
