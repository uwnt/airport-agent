# Evaluation run: `gemini-3.1-pro-preview`

Run on 2026-10-11 with `scripts/evaluate.py`: thinking level low, at most 8 tool calls per question. Each conversation is a fresh chat; the answers are as the model gave them.

| Conversation | Questions | Seconds | Tool calls | Tokens (in / out / thinking) | Cost (USD) | Numbers not found in tool results |
|---|---|---|---|---|---|---|
| [a-new-england](a-new-england.md) | 1 | 14.1 | 1 | 3,415 in / 944 out / 330 thinking | $0.0221 | 0 |
| [b-lax-vs-sna](b-lax-vs-sna.md) | 1 | 16.2 | 1 | 3,410 in / 767 out / 423 thinking | $0.0211 | 0 |
| [c-anchorage-long-haul](c-anchorage-long-haul.md) | 1 | 8.9 | 1 | 3,424 in / 215 out / 577 thinking | $0.0164 | 0 |
| [d-sfo-unmet-demand](d-sfo-unmet-demand.md) | 1 | 13.2 | 2 | 3,491 in / 714 out / 449 thinking | $0.0209 | 0 |
| [e-trap-uncovered-airport](e-trap-uncovered-airport.md) | 1 | 9.2 | 2 | 3,521 in / 203 out / 424 thinking | $0.0146 | 0 |
| [f-trap-nonsense-code](f-trap-nonsense-code.md) | 1 | 7.0 | 1 | 3,383 in / 123 out / 195 thinking | $0.0106 | 0 |
| [g-trap-roi-in-dollars](g-trap-roi-in-dollars.md) | 1 | 6.2 | 0 | 1,642 in / 80 out / 208 thinking | $0.0067 | 0 |
| [h-trap-region-switch](h-trap-region-switch.md) | 2 | 22.9 | 2 | 8,342 in / 1,484 out / 486 thinking | $0.0403 | 0 |
| [i-trap-ambiguous-place](i-trap-ambiguous-place.md) | 1 | 10.6 | 2 | 3,506 in / 443 out / 416 thinking | $0.0173 | 0 |

Average cost per question: $0.0170 (total $0.1700, 10 questions).

Prices: https://ai.google.dev/gemini-api/docs/pricing, checked 2026-10-11. Cost = input tokens x input price + (output + thinking tokens) x output price.

The token counts are those the API reports. Checked 2026-10-11: the reported input count hardly grows when a tool result is sent back (a ranking result of about 11,000 characters added about 30 input tokens), so tool results seem not to be counted, and the real input cost may be higher than shown. No cache discount is applied.

Numbers not found in tool results: numbers in the answer that appear in none of the conversation's tool results, allowing for rounding and for shares quoted as percentages. Each needs a human look; it is not automatically wrong.
