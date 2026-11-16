# STATUS

_Updated: 2026-11-16 ~07:35 IST_

## Works (verified)
- **HydraDB v0.4.0**, built from source and running locally (`make hydradb`; Bolt 7687; telemetry off).
  `make gate` passes: SelfGraph typed insert, learned route as one Cypher query, versioned supersede,
  neighbors, raw Bolt Cypher fallback (`results/gate_hydradb.json`).
- `make test`: 9 passed against live HydraDB in 22 s on a fresh store.
- `make eval`: full pipeline on HydraDB. 3 seeds × 4 rounds, 48 train / 36 held-out questions per seed, then the
  heal test, savings calculator and README update. Re-running it from the request cache reproduced A, B and
  seed 0 exactly (see run-to-run note in the README).
- Headline (held-out, after 4 rounds, mean ± std over 3 seeds): C at 1.00 accuracy with 0.67 LLM calls and 440
  input tokens per task, against B at 1.00 with 4.83 calls and 3,155 tokens. That is 86% fewer calls and tokens.
  Latency per task: 2.7 s vs 6.7 s. Vector RAG (A) reaches 0.34.
- Heal test: one on-call fact changes, the dependent route retires, C walks the graph and stays correct, the route
  rebuilds as v2 and is back to 0 LLM calls. The stale-route agent returns the superseded person.
- Dashboard (`make demo`): measured curves and tables, live ask (B vs C), live fact change, retire, rebuild,
  route library, savings calculator. Backup video: `docs/demo.mp4`.

- Packaging: `pip install -e .` installs `desirepaths` as a SelfGraph add-on; register any schema with
  `set_relations(...)`.
- CI (GitHub Actions, Python 3.11, no secrets): installs the package, runs the tests on embedded Kuzu, and checks
  that the README and savings table regenerate exactly from the committed results. Green.
- Verified from a fresh clone with no `.env`: 9 tests pass; regenerating the README from results gives no diff.
- Dashboard route view: each learned route's compiled one-query Cypher and a live run.

## Known limits (also in README "Honest notes")
- Model is `poolside/laguna-xs-2.1`, because Gemma 4 timed out on NVIDIA's API (`results/model_probe.md`).
- 6 of 108 final held-out questions fall back to the walk, all with one unseen phrasing (router miss). They are
  caught by the entity check, so the answers stay correct.
- The single dev HydraDB node slows down as namespaces accumulate; `make demo` and `make hydradb-reset` start fresh.
- A local HydraDB node, not HydraDB Cloud.

## Next (if there is time)
- Paraphrase clustering for question shapes; a route-aware router prompt for the one phrasing it misses.
- Run against HydraDB Cloud by setting `HYDRADB_URI` / `HYDRADB_TOKEN`.
