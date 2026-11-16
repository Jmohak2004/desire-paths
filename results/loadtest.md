# Load test (graph only, no LLM)

Backend **hydradb**, seed 0: 36 held-out questions × 10 passes per level. `route` = one learned-route query per question; `walk` = one neighbors query per hop along the same path.

| workload | concurrency | throughput (q/s) | p50 ms | p95 ms | p99 ms | errors | correct |
|---|---|---|---|---|---|---|---|
| route | 1 | 10.3 | 41.7 | 357.6 | 447.1 | 0 | 360/360 |
| route | 8 | 24.5 | 150.1 | 1229.7 | 1453.8 | 0 | 360/360 |
| route | 32 | 24.0 | 570.1 | 5023.3 | 5119.9 | 0 | 360/360 |
| route | 64 | 25.7 | 1115.4 | 8822.6 | 8961.2 | 0 | 360/360 |
| walk | 1 | 4.7 | 223.8 | 299.9 | 303.1 | 0 | 360/360 |
| walk | 8 | 15.1 | 527.4 | 782.8 | 843.6 | 0 | 360/360 |
| walk | 32 | 18.5 | 1786.0 | 2475.9 | 2526.5 | 0 | 360/360 |
| walk | 64 | 18.7 | 3390.9 | 4885.8 | 5279.4 | 0 | 360/360 |
