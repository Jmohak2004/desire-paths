# Results

Model `gemma-4-26b-a4b-it` (temperature 0), embeddings `nvidia/nemotron-3-embed-1b`, backend: hydradb.
Seeds [0, 1, 2]; mean ± std across seeds of per-question averages on HELD-OUT questions.

## Held-out, after 4 learning rounds

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.71 ± 0.03 | 2.52 ± 0.03 | 705 ± 9 | 28 ± 0 | 21.58 ± 0.80 | 0.0 ± 0.0 |
| B_graph | 0.99 ± 0.01 | 4.87 ± 0.05 | 3129 ± 6 | 66 ± 0 | 23.52 ± 2.75 | 3.9 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 0.54 ± 0.07 | 317 ± 37 | 9 ± 1 | 9.84 ± 1.91 | 2.4 ± 0.0 |


## Held-out, round 0 (before any learning)

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.71 ± 0.03 | 2.52 ± 0.03 | 705 ± 9 | 28 ± 0 | 21.58 ± 0.80 | 0.0 ± 0.0 |
| B_graph | 0.99 ± 0.01 | 4.87 ± 0.05 | 3129 ± 6 | 66 ± 0 | 23.52 ± 2.75 | 3.9 ± 0.0 |
| C_desire | 0.99 ± 0.01 | 4.87 ± 0.05 | 3129 ± 6 | 66 ± 0 | 23.78 ± 2.79 | 3.9 ± 0.0 |


## Learning curve (held-out, per round)

Accuracy within a budget of 1 LLM call per question (a hard cap: an answer that needs more calls counts as wrong). A and B hold no learning state, so their values are the same every round.

| round | C: accuracy @ 1 call | C: accuracy @ 2 calls | C: accuracy (no cap) | C: LLM calls / q | C: tokens / correct answer | C: routed share | B: accuracy @ 1 call | A: accuracy @ 1 call |
|---|---|---|---|---|---|---|---|---|
| 0 | **0.00 ± 0.00** | 0.00 | 0.99 ± 0.01 | 4.87 ± 0.05 | 3226 | 0.00 | 0.00 | 0.02 |
| 1 | **0.28 ± 0.08** | 0.28 | 0.99 ± 0.01 | 4.24 ± 0.34 | 2500 | 0.28 | 0.00 | 0.02 |
| 2 | **0.83 ± 0.14** | 0.83 | 1.00 ± 0.00 | 1.22 ± 0.79 | 747 | 0.83 | 0.00 | 0.02 |
| 3 | **0.95 ± 0.01** | 0.95 | 1.00 ± 0.00 | 0.54 ± 0.07 | 326 | 0.95 | 0.00 | 0.02 |
| 4 | **0.95 ± 0.01** | 0.95 | 1.00 ± 0.00 | 0.54 ± 0.07 | 326 | 0.95 | 0.00 | 0.02 |

A and B hold no learning state: measured once per seed (round 0) and drawn flat across rounds.
