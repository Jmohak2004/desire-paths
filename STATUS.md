# STATUS

_Updated: 2026-11-16 ~02:05 IST_

## Works (verified by tests)
- Seeded synthetic enterprise graph (2,580 nodes / 5,080 edges at default size), 6 question templates (2–4 hops,
  one with a reverse hop), gold answers computed from the graph, train/held-out with disjoint start entities and an
  unseen phrasing in held-out (`bench/gen.py`).
- SelfGraph backend: typed versioned inserts, keyword-seed search, neighbors, single-query route execution
  (`desirepaths/backend.py`). Verified on embedded Kuzu.
- Route learning (`desirepaths/routes.py`): verified multi-hypothesis meta-paths per trace, shape-attached
  promotion (coincidental shortcuts and redundant detours are rejected), provenance (relation id + revision),
  retirement on fact change, revalidation/rebuild as a new version.
- Agents A/B/C (`desirepaths/agents.py`) and the eval runner (`eval/run.py`); pipeline tested end to end with a
  scripted oracle LLM (no API spend).
- `make test`: 7 passed.

## Broken / not yet verified
- **HydraDB not reached yet.** No HydraDB credentials are set on this machine and a local build is impossible
  (disk ~1 GB free, no Docker). `make gate` (`scripts/gate_hydradb.py`) is ready and exits 2 until
  `HYDRADB_URI` / `HYDRADB_TOKEN` are set. The HydraDB Cypher dialect (`Entity` / `RELATES`) is taken from
  SelfGraph's HydraDBStore source and is untested against a live node.
- **No live LLM numbers yet.** `NVIDIA_API_KEY` is not set. Model pinned: `google/gemma-4-31b-it`, temperature 0;
  embeddings `nvidia/llama-3.2-nv-embedqa-1b-v1` (dim 384).

## Next
1. NVIDIA key -> `make eval-quick` smoke run -> full `make eval` (3 seeds).
2. Heal test (`eval/heal.py`), savings calculator, dashboard.
3. README, demo script, upstream SelfGraph issue draft.
