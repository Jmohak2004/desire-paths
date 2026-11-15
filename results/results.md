# Results

Model `poolside/laguna-xs-2.1` (temperature 0), embeddings `nvidia/nemotron-3-embed-1b`, backend: kuzu (embedded SelfGraph store; HydraDB not configured).
Seeds [0]; mean ± std across seeds of per-question averages on HELD-OUT questions.

## Held-out, after 2 learning rounds

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.75 ± 0.00 | 2.50 ± 0.00 | 742 ± 0 | 32 ± 0 | 2.08 ± 0.00 | 0.0 ± 0.0 |
| B_graph | 1.00 ± 0.00 | 4.83 ± 0.00 | 3153 ± 0 | 77 ± 0 | 3.06 ± 0.00 | 3.8 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 1.00 ± 0.00 | 551 ± 0 | 17 ± 0 | 0.81 ± 0.00 | 2.0 ± 0.0 |


## Held-out, round 0 (before any learning)

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.75 ± 0.00 | 2.50 ± 0.00 | 742 ± 0 | 32 ± 0 | 2.08 ± 0.00 | 0.0 ± 0.0 |
| B_graph | 1.00 ± 0.00 | 4.83 ± 0.00 | 3153 ± 0 | 77 ± 0 | 3.06 ± 0.00 | 3.8 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 4.83 ± 0.00 | 3153 ± 0 | 77 ± 0 | 3.81 ± 0.00 | 3.8 ± 0.0 |


## C learning curve (held-out, per round)

| round | accuracy | LLM calls / q | input tok / q | routed share |
|---|---|---|---|---|
| 0 | 1.00 ± 0.00 | 4.83 ± 0.00 | 3153 | 0.00 |
| 1 | 1.00 ± 0.00 | 5.00 ± 0.00 | 2798 | 0.17 |
| 2 | 1.00 ± 0.00 | 1.00 ± 0.00 | 551 | 1.00 |

A and B hold no learning state: measured once per seed (round 0) and drawn flat across rounds.
