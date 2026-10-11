# Evaluation run: `gemini-3.8-flash`

Run on 2026-10-11 with `scripts/evaluate.py`: thinking level low, at most 8 tool calls per question. Each conversation is a fresh chat; the answers are as the model gave them.

| Conversation | Questions | Seconds | Tool calls | Tokens (in / out / thinking) | Cost (USD) | Numbers not found in tool results |
|---|---|---|---|---|---|---|
| [a-new-england](a-new-england.md) | 1 | 11.5 | 1 | 3,307 in / 1,202 out / 0 thinking | $0.0070 | 0 |
| [b-lax-vs-sna](b-lax-vs-sna.md) | 1 | 15.9 | 5 | 3,416 in / 1,368 out / 0 thinking | $0.0077 | 0 |
| [c-anchorage-long-haul](c-anchorage-long-haul.md) | 1 | 9.3 | 1 | 3,319 in / 251 out / 0 thinking | $0.0034 | 0 |
| [d-sfo-unmet-demand](d-sfo-unmet-demand.md) | 1 | 10.9 | 2 | 3,328 in / 1,069 out / 0 thinking | $0.0065 | 0 |
| [e-trap-uncovered-airport](e-trap-uncovered-airport.md) | 1 | 6.5 | 3 | 3,359 in / 246 out / 0 thinking | $0.0034 | 0 |
| [f-trap-nonsense-code](f-trap-nonsense-code.md) | 1 | 14.3 | 3 | 6,716 in / 614 out / 0 thinking | $0.0073 | 0 |
| [g-trap-roi-in-dollars](g-trap-roi-in-dollars.md) | 1 | 2.9 | 0 | 1,642 in / 59 out / 0 thinking | $0.0015 | 0 |
| [h-trap-region-switch](h-trap-region-switch.md) | 2 | 22.2 | 2 | 9,306 in / 2,585 out / 0 thinking | $0.0167 | 0 |
| [i-trap-ambiguous-place](i-trap-ambiguous-place.md) | 1 | 7.2 | 2 | 3,316 in / 600 out / 0 thinking | $0.0047 | 0 |

Average cost per question: $0.0058 (total $0.0583, 10 questions).

Prices: https://ai.google.dev/gemini-api/docs/pricing, checked 2026-10-11. Cost = input tokens x input price + (output + thinking tokens) x output price.

The token counts are those the API reports. Checked 2026-10-11: the reported input count hardly grows when a tool result is sent back (a ranking result of about 11,000 characters added about 30 input tokens), so tool results seem not to be counted, and the real input cost may be higher than shown. No cache discount is applied.

Numbers not found in tool results: numbers in the answer that appear in none of the conversation's tool results, allowing for rounding and for shares quoted as percentages. Each needs a human look; it is not automatically wrong.
