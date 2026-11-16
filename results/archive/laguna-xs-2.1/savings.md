# Savings calculator

Per-task tokens are measured (held-out, final learning round, mean over seeds). Prices are inputs.

| agent | accuracy | LLM calls / task | input tok / task | output tok / task |
|---|---|---|---|---|
| A_vector | 0.34 | 2.13 | 601 | 27 |
| B_graph | 1.00 | 4.83 | 3155 | 77 |
| C_desire | 1.00 | 0.67 | 440 | 12 |

Cost per 1,000 tasks (USD), and per month at 100,000 tasks:

| price point ($/1M in / out) | A_vector | B_graph | C_desire | C vs B saving | C one-time learning |
|---|---|---|---|---|---|
| small-open-model (0.10 / 0.40) | $0.071 ($7/mo) | $0.346 ($35/mo) | $0.049 ($5/mo) | 86% | $0.010 |
| claude-haiku-5-5 list (0.10 / 0.50) | $0.074 ($7/mo) | $0.354 ($35/mo) | $0.050 ($5/mo) | 86% | $0.010 |
| claude-sonnet-5-5 list (2.00 / 10.00) | $1.474 ($147/mo) | $7.081 ($708/mo) | $0.995 ($100/mo) | 86% | $0.204 |
| claude-opus-5-5 list (4.00 / 20.00) | $2.949 ($295/mo) | $14.162 ($1,416/mo) | $1.990 ($199/mo) | 86% | $0.408 |
