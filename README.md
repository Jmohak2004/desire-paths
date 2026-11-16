# Desire Paths

[![tests](https://github.com/Jmohak2004/desire-paths/actions/workflows/test.yml/badge.svg)](https://github.com/Jmohak2004/desire-paths/actions/workflows/test.yml)

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
## Results (measured, `make eval`)

Held-out questions about entities never seen in training. Seeds [0, 1, 2] (mean ± std across seeds), model `poolside/laguna-xs-2.1` at temperature 0, backend **hydradb**, generated 2026-11-16 04:16:19.

- After 4 learning rounds, **C uses 86% fewer LLM calls and 86% fewer tokens per task than B** (the same agent without routes), at accuracy 1.00 vs 1.00.
- Iterative vector RAG (A) reaches 0.34 accuracy on the same questions.

![learning curve](docs/img/curve.png)

#### Held-out, after 4 learning rounds

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.34 ± 0.05 | 2.13 ± 0.08 | 601 ± 31 | 27 ± 1 | 1.90 ± 0.50 | 0.0 ± 0.0 |
| B_graph | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 ± 26 | 77 ± 0 | 6.70 ± 0.58 | 3.8 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 0.67 ± 0.05 | 440 ± 27 | 12 ± 1 | 2.70 ± 0.31 | 2.5 ± 0.0 |


#### Held-out, round 0 (before any learning)

| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |
|---|---|---|---|---|---|---|
| A_vector | 0.34 ± 0.05 | 2.13 ± 0.08 | 601 ± 31 | 27 ± 1 | 1.90 ± 0.50 | 0.0 ± 0.0 |
| B_graph | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 ± 26 | 77 ± 0 | 6.70 ± 0.58 | 3.8 ± 0.0 |
| C_desire | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 ± 26 | 77 ± 0 | 6.64 ± 0.61 | 3.8 ± 0.0 |


#### C learning curve (held-out, per round)

| round | accuracy | LLM calls / q | input tok / q | routed share |
|---|---|---|---|---|
| 0 | 1.00 ± 0.00 | 4.83 ± 0.00 | 3155 | 0.00 |
| 1 | 1.00 ± 0.00 | 4.63 ± 0.49 | 2720 | 0.21 |
| 2 | 1.00 ± 0.00 | 1.74 ± 0.34 | 1118 | 0.78 |
| 3 | 1.00 ± 0.00 | 0.67 ± 0.05 | 440 | 0.94 |
| 4 | 1.00 ± 0.00 | 0.67 ± 0.05 | 440 | 0.94 |

A and B hold no learning state: measured once per seed (round 0) and drawn flat across rounds.

### Heal test (`results/heal.json`)

Question: “Who is currently on call for the team that owns the project Arjun Mehta works on?”. One fact changes: on-call for Insights Platform, Chloe Ilic → Chloe Jansen.

| phase | Desire Paths (C) | LLM calls | stale-route agent |
|---|---|---|---|
| before change | Chloe Ilic ✓ (route Rc346) | 0 | Chloe Ilic ✓ |
| after change template retired | Chloe Jansen ✓ (fallback walk) | 6 | Chloe Ilic ✗ |
| after rebuild | Chloe Jansen ✓ (route Rc346) | 0 | Chloe Ilic ✗ |

Retired: Rc346 v1. Rebuilt: Rc346 v2.

### Savings calculator (`results/savings.md`)

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

HydraDB gate (`make gate`): **passed**: selfgraph_insert, route_single_query, versioned_supersede, neighbors, raw_cypher_fallback.
<!-- RESULTS:END -->

## Demo

Backup recording of the live dashboard: [`docs/demo.mp4`](docs/demo.mp4), made with `make record`. Every answer
in it was computed live against HydraDB. The 60-second script is in [`docs/demo_script.md`](docs/demo_script.md).

| same held-out question: B walks (5 LLM calls) | C uses the learned route (0 LLM calls, 1 graph query) |
|---|---|
| ![B](docs/img/ask_b.png) | ![C](docs/img/ask_c.png) |

| one fact changes: route retires, C walks and is still right | rebuilt route v2: back to 0 LLM calls, new fact |
|---|---|
| ![after change](docs/img/after_change.png) | ![after rebuild](docs/img/after_rebuild.png) |

Every learned route compiles to a single HydraDB query. The dashboard's route library shows each route's support,
the relation versions it depends on, its Cypher, and a live run:

![route view](docs/img/route_view.png)

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
make setup                                  # venv + deps (Python 3.10+; CI runs 3.11, dev box ran 3.13)
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
make demo        # fresh HydraDB node + dashboard in one command (what to run before recording)
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
- **Known router miss.** 6 of the 108 final held-out questions fall back to the full walk, and all 6 use the same
  unseen phrasing ("I need to page someone about X's project…"). The router picks the wrong route with entity
  "X's project"; the entity check rejects it, so C walks the graph and still answers correctly. It costs about 6 LLM
  calls instead of 1.
- **Run-to-run variation.** HydraDB's keyword search can return tied scores in a different order between runs.
  When a question's entity falls out of the top 5, the shape index misses and the router makes one extra LLM call.
  Re-running `make eval` from the cache reproduced A, B and seed 0 exactly. C's final calls per task were 0.65 on
  the first run and 0.67 on the rerun; accuracy was unchanged.
- **Latency** = measured LLM time per call (NVIDIA free tier, so queueing is included) plus graph time measured on
  every run. Held-out questions are scored one at a time.
- **HydraDB store growth.** Every run loads the graph into a fresh namespace, and SelfGraph applies the namespace
  as a filter. After many runs the single dev node slowed down a lot: the test suite took 19 minutes, with 2 errors.
  On a fresh store it passes in 22 s. `make demo` starts from a fresh store, and `make hydradb-reset` wipes it.
- **HydraDB** here is a single local v0.4.0 node built from source, not HydraDB Cloud. The same code points at any
  Bolt endpoint via `HYDRADB_URI`.

## Use it as a library (SelfGraph add-on)

```bash
pip install -e ".[agents,kuzu]"     # or just the core: pip install -e .
```

```python
from desirepaths import GraphBackend, RouteLibrary, Trace, make_selfgraph, set_relations, verified_paths

set_relations([("WORKS_ON", "Person", "Project", 1), ("OWNED_BY", "Project", "Team", 1), ...])  # your schema
sg, dialect, ns = make_selfgraph("graph.kuzu", schema, fresh=False)   # HydraDB when HYDRADB_URI is set
graph = GraphBackend(sg, dialect, namespace=ns)
lib = RouteLibrary(min_support=3)

# after your agent answers: edges it looked at, entities it searched, answer ids, whether it was right
start, candidates = await verified_paths(graph, explored_edges, searched_ids, answer_ids)
lib.observe(Trace(question, start, start_type, start_name, answer_ids, success, candidates))
lib.promote()

rows = await graph.run_route(lib.active()[0].hops, new_entity_id)   # ONE query, answers + provenance
lib.on_relation_change(retired_relation_id); await lib.revalidate(graph)
```

`desirepaths.agents.DesirePaths` wires all of this into an agent: shape index, then router, then graph-walk
fallback, with online learning.

## Open source

`desirepaths/` is structured as an add-on to SelfGraph. The draft upstream proposal is in
[`docs/upstream_issue.md`](docs/upstream_issue.md). The 60-second demo script is in
[`docs/demo_script.md`](docs/demo_script.md).

License: Apache-2.0.
