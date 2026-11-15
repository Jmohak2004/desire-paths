# STATUS

_Updated: 2026-11-16 ~03:05 IST_

## Works (verified)
- **HydraDB v0.4.0**, built from source and running locally (`make hydradb`, Bolt 7687, telemetry off).
  `make gate` passes all four checks: SelfGraph typed insert, learned route as one Cypher query, versioned
  supersede, raw Bolt Cypher fallback (`results/gate_hydradb.json`).
- `make test`: 8 passed, run against live HydraDB. Covers route learning, single-query execution on unseen
  entities, rejection of coincidental shortcuts, retire-and-rebuild on a fact change, library round-trip, and the
  end-to-end pipeline.
- HydraDB and Kuzu return identical search and neighbor results on 12/12 checked questions; routes return gold
  12/12. A route query on HydraDB takes about 7 ms.
- Live dashboard on HydraDB: ask (C routes in 1 LLM call), fact change, retire, fallback, rebuild v2, route again.
- Agents A/B/C on `poolside/laguna-xs-2.1` (Gemma 4 was unusable: see `results/model_probe.md`).

## Running
- Full eval on HydraDB: 3 seeds × 4 rounds, 48 train / 36 held-out per seed.

## Known limits
- Vector RAG baseline is weak (~0.4 accuracy). Two stronger prompts were tried and did not help (recorded).
- Question shapes are exact masked strings; paraphrase clustering is future work.
- Single local HydraDB node, not HydraDB Cloud.

## Next
- heal test, calculator, README numbers, demo recording.
