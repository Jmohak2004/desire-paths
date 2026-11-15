# Desire Paths

**Agent cost per task falls as your graph is used.**

Desire Paths is a context layer on [HydraDB](https://github.com/hydra-db/hydradb) and
[SelfGraph](https://github.com/hydra-db/selfgraph). It watches how agents walk the graph to answer multi-hop
questions and learns **route templates** from the walks that worked. A template is a typed path, such as
`(Person)-[WORKS_ON]->()-[OWNED_BY]->()-[ON_CALL]->()`. On a **new** question about entities it has never seen,
the agent runs the template as **one HydraDB query** instead of one LLM call per hop. Each template records the
relation ids and versions it was learned from. When one of those facts changes, the dependent templates retire and
rebuild themselves against the current graph.

> Desire path (n.): the trail worn into the grass by people taking the route the pavement should have taken.

<!-- RESULTS:START -->
_Run `make eval` to fill this section from `results/`._
<!-- RESULTS:END -->

## Why this earns its place over a vector store

A vector store retrieves passages that *look like* the question. A multi-hop question ("who is on call for the team
that owns the project Ana works on?") needs facts that look nothing like it: the on-call person's snippet doesn't
mention Ana. Iterative vector RAG has to guess its way through the hops (baseline A below).

The graph agent (B) gets the hops right but pays one LLM call per hop, every time. Desire Paths (C) keeps B's
accuracy and learns the *shape* of the walk, so after a few uses that shape costs one call. It needs three things a
vector store doesn't have:

- **typed relations**, so a route generalises to any entity of the start type;
- **one-query multi-hop execution**, so a learned route skips the LLM calls for the intermediate hops;
- **versioned facts**, so a route knows when the facts behind it changed.

## How it works

```
 question ─► keyword search (1 graph call) ─► masked shape known? ─yes─► its route ─► ONE Cypher query ─► answer
                                                   │ no                  (0 LLM calls; any entity of that type)
                                                   ▼
                        router (1 LLM call) picks a route + names the start entity ─► entity check ─► ONE query
                                                   │ no route / not resolved
                                                   ▼
                     graph agent walks hop by hop (search / neighbors, 1 LLM call per step)
                                                   │ success signal
                                                   ▼
   trace ─► candidate typed walks through the explored edges ─► verify each with one query (must return exactly the answer)
                                                   │
                                                   ▼
   RouteLibrary: per question shape (the question with its entity masked by type), a meta-path is attached only if it
   explains ≥80% of that shape's successful traces (rejects coincidences: "the PR author happens to be the manager");
   shortest such path wins; promote at support ≥3. Provenance = (relation id, revision) of every supporting trace.
                                                   │
   SelfGraph supersedes a fact ─► on_relation_change(rel_id) ─► dependent templates RETIRE
                                                   │
                       revalidate(): re-bind each support trace on the current graph ─► template vN+1
```

A question shape seen in training maps straight to its route, even when the entity is new, so those questions cost
zero LLM calls. A new phrasing goes through the router, one LLM call. A router mistake during training is logged
as a misroute and does not demote the route. A wrong answer through the shape index does count against the route.

| module | what it does |
|---|---|
| [`desirepaths/routes.py`](desirepaths/routes.py) | traces, candidate walks, verification, shape-attached promotion, provenance, retirement, revalidation |
| [`desirepaths/backend.py`](desirepaths/backend.py) | SelfGraph over HydraDB (or embedded Kuzu); compiles a route to one Cypher query in either dialect |
| [`desirepaths/agents.py`](desirepaths/agents.py) | A vector RAG, B graph agent, C Desire Paths: same LLM, same questions |
| [`desirepaths/llm.py`](desirepaths/llm.py) | one pinned model at temperature 0, metering, request cache that replays measured usage |
| [`bench/gen.py`](bench/gen.py) | seeded synthetic enterprise graph (2,580 nodes / 5,080 edges), 6 question templates, gold answers |
| [`eval/`](eval) | `run.py` (A vs B vs C, rounds, seeds), `heal.py`, `calculator.py` |
| [`dashboard/`](dashboard) | FastAPI + one page: curves, table, live ask, live fact change, route library, calculator |
| [`scripts/gate_hydradb.py`](scripts/gate_hydradb.py) | proves custom writes + Cypher on HydraDB (SelfGraph path and raw Bolt fallback) |

## Run it

```bash
make setup                                  # venv + deps (Python 3.10+)
cp .env.example .env                        # add NVIDIA_API_KEY; HYDRADB_URI / HYDRADB_TOKEN

# HydraDB v0.4.0 local node (no Docker needed; ~6 min build on Apple silicon)
brew install just cmake pkg-config llvm suite-sparse coreutils cleishm/neo4j/libcypher-parser
git clone --branch v0.4.0 https://github.com/hydra-db/hydradb ~/hydradb
(cd ~/hydradb && BINDGEN_EXTRA_CLANG_ARGS="-I$(brew --prefix)/include" LIBRARY_PATH="$(brew --prefix)/lib" \
   cargo build --locked --release --features server-runtime --bin graph-node)
make hydradb                                # terminal 1: Bolt 127.0.0.1:7687 (telemetry off)
# .env: HYDRADB_URI=bolt://127.0.0.1:7687  HYDRADB_TOKEN=local-development-token-32-bytes

make gate        # custom nodes/edges + Cypher on HydraDB  -> results/gate_hydradb.json
make test        # route learning, execution, retirement, pipeline (runs on HydraDB when configured)
make eval        # 3 seeds x 4 rounds, heal test, calculator -> results/
make dashboard   # http://127.0.0.1:8000
make record      # backup demo video from the live dashboard -> docs/demo.mp4
```

Without `HYDRADB_URI`, everything runs on SelfGraph's embedded Kuzu store, and the results record which backend
was used. `make eval` replays LLM responses from `results/cache/llm.jsonl` when the exact request was already made.
The cache replays the token usage and latency measured when the call was made live. `DP_CACHE=off` forces live
calls.

## Honest notes

- **Model.** The plan was `google/gemma-4-31b-it` on NVIDIA's API. During the build window it took 112–200 s per
  call or timed out (evidence: [`results/model_probe.md`](results/model_probe.md)). All three agents therefore use
  `poolside/laguna-xs-2.1`, the fastest model that solved the graph-agent probe, at temperature 0.
  `DP_MODEL=google/gemma-4-31b-it make eval` switches back.
- **Embeddings** for baseline A: `nvidia/nemotron-3-embed-1b`, the only NVIDIA embedder that served this key.
  We tried two stronger A prompts; neither beat the shipped one (see `results/model_probe.md`).
- **A and B have no learning state**, so their numbers cannot change between rounds. They are measured once per
  seed and drawn flat; the results say so.
- **Train/held-out.** Held-out questions use start entities never seen in train, plus a phrasing never seen in
  train. Route learning only ever sees train questions; held-out scoring has learning frozen.
- **Success signal.** In training, success comes from the gold answer. In production it would be user feedback or
  a verifier.
- **Question shapes** are the question text with the entity masked, matched exactly. Held-out questions include a
  phrasing never seen in train; those go through the one-call router. Clustering paraphrases is future work.
- **HydraDB** here is a single local v0.4.0 node built from source, not HydraDB Cloud. The same code points at any
  Bolt endpoint via `HYDRADB_URI`.

## Open source

`desirepaths/` is structured as an add-on to SelfGraph. The draft upstream proposal is in
[`docs/upstream_issue.md`](docs/upstream_issue.md). The 60-second demo script is in
[`docs/demo_script.md`](docs/demo_script.md).

License: Apache-2.0.
