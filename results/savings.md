# Savings calculator

Per-task tokens are measured (held-out, final learning round, mean over seeds). Prices are inputs.

| agent | accuracy | LLM calls / task | input tok / task | output tok / task |
|---|---|---|---|---|
| A_vector | 0.71 | 2.52 | 705 | 28 |
| B_graph | 0.99 | 4.87 | 3129 | 66 |
| C_desire | 1.00 | 0.54 | 317 | 9 |

Cost per 1,000 tasks (USD), and per month at 100,000 tasks:

| price point ($/1M in / out) | A_vector | B_graph | C_desire | C vs B saving | C one-time learning |
|---|---|---|---|---|---|
| small-open-model (0.10 / 0.40) | $0.082 ($8/mo) | $0.340 ($34/mo) | $0.035 ($4/mo) | 90% | $0.009 |
| claude-haiku-5-5 list (0.10 / 0.50) | $0.085 ($8/mo) | $0.346 ($35/mo) | $0.036 ($4/mo) | 90% | $0.009 |
| claude-sonnet-5-5 list (2.00 / 10.00) | $1.693 ($169/mo) | $6.922 ($692/mo) | $0.725 ($72/mo) | 90% | $0.185 |
| claude-opus-5-5 list (4.00 / 20.00) | $3.386 ($339/mo) | $13.845 ($1,384/mo) | $1.449 ($145/mo) | 90% | $0.371 |
