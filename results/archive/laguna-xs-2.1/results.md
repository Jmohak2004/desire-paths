# Results

Model `poolside/laguna-xs-2.1` (temperature 0), embeddings `nvidia/nemotron-3-embed-1b`, backend: hydradb.
Seeds [0, 1, 2]; mean ± std across seeds of per-question averages on HELD-OUT questions.

## Held-out, after 4 learning rounds

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.34 ± 0.05 | 2.13 ± 0.08 | 601 ± 31 | 27 ± 1 | 1.90 ± 0.50 | 0.0 ± 0.0 |
| B_graph | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 ± 26 | 77 ± 0 | 6.70 ± 0.58 | 3.8 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 0.67 ± 0.05 | 440 ± 27 | 12 ± 1 | 2.70 ± 0.31 | 2.5 ± 0.0 |


## Held-out, round 0 (before any learning)

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.34 ± 0.05 | 2.13 ± 0.08 | 601 ± 31 | 27 ± 1 | 1.90 ± 0.50 | 0.0 ± 0.0 |
| B_graph | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 ± 26 | 77 ± 0 | 6.70 ± 0.58 | 3.8 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 ± 26 | 77 ± 0 | 6.64 ± 0.61 | 3.8 ± 0.0 |


## Learning curve (held-out, per round)

Accuracy within a budget of 1 LLM call per question (a hard cap: an answer that needs more calls counts as wrong). A and B hold no learning state, so their values are the same every round.

| round | C: accuracy @ 1 call | C: accuracy @ 2 calls | C: accuracy (no cap) | C: LLM calls / q | C: tokens / correct answer | C: routed share | B: accuracy @ 1 call | A: accuracy @ 1 call |
|---|---|---|---|---|---|---|---|---|
| 0 | **0.00 ± 0.00** | 0.00 | 1.00 ± 0.00 | 4.83 ± 0.00 | 3232 | 0.00 | 0.00 | 0.02 |
| 1 | **0.21 ± 0.09** | 0.21 | 1.00 ± 0.00 | 4.63 ± 0.49 | 2786 | 0.21 | 0.00 | 0.02 |
| 2 | **0.78 ± 0.08** | 0.78 | 1.00 ± 0.00 | 1.74 ± 0.34 | 1145 | 0.78 | 0.00 | 0.02 |
| 3 | **0.94 ± 0.00** | 0.94 | 1.00 ± 0.00 | 0.67 ± 0.05 | 451 | 0.94 | 0.00 | 0.02 |
| 4 | **0.94 ± 0.00** | 0.94 | 1.00 ± 0.00 | 0.67 ± 0.05 | 451 | 0.94 | 0.00 | 0.02 |

A and B hold no learning state: measured once per seed (round 0) and drawn flat across rounds.
