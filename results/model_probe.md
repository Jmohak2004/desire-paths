# Model probe (2026-11-16, ~02:15 IST, NVIDIA integrate API, this account's key)

Requested model: `google/gemma-4-31b-it`. Re-checked 07:19 IST: still timed out at 60 s.

1. Single `{"ok": true}` call: 118.9 s. Then 6 calls: one 112 s, five timed out at 200 s. Later probe: timed out at 60 s.
2. Every other chat model on the key, one call each, 45 s timeout. Most older ids return 404 or 410 (retired).
   Responding: `poolside/laguna-xs-2.1` 0.4 s, `nvidia/nemotron-3.5-bolt-e4b` 0.4 s,
   `nvidia/nemotron-3.5-lightning-30b-a3b` 0.5 s (empty content), `minimaxai/minimax-m3.1-flash` 8.9 s.
   Timed out: `deepseek-ai/deepseek-v4.1-flash`, `openai/gpt-oss-20b`, `z-ai/glm-5.3-flash`.
3. Graph agent B on 6 held-out questions (one per template, seed 0), temperature 0:

| model | correct | LLM calls / q | latency / q |
|---|---|---|---|
| poolside/laguna-xs-2.1 | 6/6 | 4.8 | 4.8 s |
| minimaxai/minimax-m3.1-flash | 3/6 | 2.8 | 31.5 s (429 rate limits) |
| nvidia/nemotron-3.5-bolt-e4b | 2/6 | 7.0 | 2.9 s |
| nvidia/nemotron-3.5-lightning-30b-a3b | 0/6 | 8.0 | 16.3 s |

Decision: every agent in the measured eval uses `poolside/laguna-xs-2.1` at temperature 0. Switch with `DP_MODEL=...`.
Embeddings: `nvidia/nemotron-3-embed-1b` (2048-d), the only embedding model that answered on this key.

## Vector-RAG baseline prompt check (seed 0, 12 held-out questions, same model)

A answered too early (after 1-2 retrievals) with a wrong intermediate entity. We tried two stronger prompts to make
sure the baseline is not a strawman:

| A prompt variant | correct on the 12-question subset |
|---|---|
| v1 (shipped): answer or issue a follow-up search, 3 rounds | 3/12 (15/36 on the full held-out set) |
| v2: "check that every link of the chain is retrieved", 4 rounds | 2/12 |
| v3: cite the chain of facts first, then answer or search, 4 rounds | 2/12 |

Neither variant helped, so the eval keeps v1.
