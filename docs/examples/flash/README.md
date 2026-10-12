# Evaluation run: `gemini-3.8-flash`

Run on 2026-10-12 with `scripts/evaluate.py`: thinking level low, at most 8 tool calls per question. Each conversation is a fresh chat; the answers are as the model gave them.

| Conversation | Questions | Seconds | Tool calls | Tokens reported (in / out / thinking) | Tool-result input tokens (estimated) | Cost reported (USD) | Cost estimated with tool results (USD) | Numbers not found in tool results |
|---|---|---|---|---|---|---|---|---|
| [a-new-england](a-new-england.md) | 1 | 8.6 | 1 | 3,855 in / 985 out / 0 thinking | 4,196 | $0.0066 | $0.0097 | 0 |
| [b-lax-vs-sna](b-lax-vs-sna.md) | 1 | 10.3 | 4 | 4,287 in / 1,004 out / 335 thinking | 4,402 | $0.0082 | $0.0115 | 0 |
| [c-anchorage-long-haul](c-anchorage-long-haul.md) | 1 | 4.2 | 1 | 3,978 in / 261 out / 111 thinking | 202 | $0.0044 | $0.0045 | 0 |
| [d-sfo-unmet-demand](d-sfo-unmet-demand.md) | 1 | 7.6 | 2 | 3,876 in / 1,135 out / 0 thinking | 2,325 | $0.0072 | $0.0089 | 0 |
| [e-trap-uncovered-airport](e-trap-uncovered-airport.md) | 1 | 4.3 | 3 | 3,907 in / 299 out / 0 thinking | 138 | $0.0041 | $0.0042 | 0 |
| [f-trap-nonsense-code](f-trap-nonsense-code.md) | 1 | 8.0 | 2 | 5,820 in / 552 out / 0 thinking | 770 | $0.0064 | $0.0070 | 0 |
| [g-trap-roi-in-dollars](g-trap-roi-in-dollars.md) | 1 | 1.9 | 0 | 1,916 in / 78 out / 0 thinking | 0 | $0.0017 | $0.0017 | 0 |
| [h-trap-region-switch](h-trap-region-switch.md) | 2 | 12.5 | 2 | 9,248 in / 1,562 out / 0 thinking | 15,828 | $0.0128 | $0.0247 | 0 |
| [i-trap-ambiguous-place](i-trap-ambiguous-place.md) | 1 | 6.0 | 3 | 3,891 in / 647 out / 0 thinking | 2,359 | $0.0053 | $0.0071 | 0 |

Average cost per question, reported: $0.0057 (total $0.0567, 10 questions).
Average cost per question, estimated with tool results: $0.0079 (total $0.0794, 10 questions).

Prices: https://ai.google.dev/gemini-api/docs/pricing, checked 2026-10-11. Cost = input tokens x input price + (output + thinking tokens) x output price.

Reported: the token counts the API reports. Checked 2026-10-11, the reported input count hardly grows when a tool result is sent back (a ranking result of about 11,000 characters added 27 input tokens), so tool results seem not to be counted. Estimated with tool results: before each model call, every tool result already in the conversation is counted with the API's token counter and added to that call's input, because each model call resends the whole conversation, so a tool result is billed again on every later call (a follow-up question included). It is an estimate: the result is counted as plain text, without the framing around it. No cache discount is applied to either.

Numbers not found in tool results: numbers in the answer that appear in none of the conversation's tool results, allowing for rounding and for shares quoted as percentages. Each needs a human look; it is not automatically wrong.
