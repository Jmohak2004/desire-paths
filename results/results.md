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


## C learning curve (held-out, per round)

| round | accuracy | LLM calls / q | input tok / q | routed share |
|---|---|---|---|---|
| 0 | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 | 0.00 |
| 1 | 1.00 ± 0.00 | 4.63 ± 0.49 | 2720 | 0.21 |
| 2 | 1.00 ± 0.00 | 1.74 ± 0.34 | 1118 | 0.78 |
| 3 | 1.00 ± 0.00 | 0.67 ± 0.05 | 440 | 0.94 |
| 4 | 1.00 ± 0.00 | 0.67 ± 0.05 | 440 | 0.94 |

A and B hold no learning state: measured once per seed (round 0) and drawn flat across rounds.
