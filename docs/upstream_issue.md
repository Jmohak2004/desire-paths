# Upstream proposal for hydra-db/selfgraph

**Title:** Proposal: learned route templates (`selfgraph.routes`): retrieval that gets cheaper with use

## Summary

SelfGraph already gives agents keyword-seeded traversal and versioned relations. Agents that answer multi-hop
questions still pay one LLM call per hop, every time, even for question shapes they have answered a hundred times.

This proposal adds an optional module that learns **route templates** from successful traversals and executes them
as **one Cypher query**. Each template carries **provenance** (the relation ids and revisions it was learned from),
so SelfGraph's existing supersede/versioning machinery retires a template when a fact it depends on changes.
A reference implementation lives in [`desirepaths/`](../desirepaths) (built on SelfGraph 0.2.1).

## Why it fits SelfGraph

- It needs no vector store. Routes are typed meta-paths over SelfGraph's ontology: relation types plus direction,
  starting from an entity type.
- It reuses `relations.versions()` and `is_current`. Retirement is driven by the same supersede events SelfGraph
  already writes.
- It generalises to entities never seen in training, because it binds types, not instances. It is not an answer cache.

## Proposed API (sketch)

```python
from selfgraph.routes import RouteLibrary, verified_paths

lib = RouteLibrary(min_support=3, min_success=0.8)

# after an agent answers: the edges it looked at, the entities it searched, the answer ids, success signal
start, candidates = await verified_paths(graph, explored_edges, searched_ids, answer_ids)
lib.observe(Trace(question, start, ..., success=True, candidates=candidates))
lib.promote()

rows = await graph.routes.run(lib.get("R3"), start_id)      # one Cypher query, returns answers + provenance
retired = lib.on_relation_change(relation_id)                # hook on supersede/update
rebuilt = await lib.revalidate(graph)                        # re-bind support to current facts, new version
```

## What we learned building it (and what upstream would make easier)

1. **Ambiguous explanations.** The shortest path through explored edges is often wrong. For example, "any member of
   the team" also reaches the on-call person. We verify each candidate meta-path by executing it and require that it
   return exactly the answer. Coincidental shortcuts, such as "the PR author is also the manager", survive one trace
   but not cross-trace support: a path must explain ≥80% of a question shape's traces. Upstream could expose a
   `graph.paths.verify(meta_path, start, expected)` primitive.
2. **Walks, not simple paths.** Real routes revisit entities (author → team → manager can return to the same
   person), so candidate enumeration uses bounded walks with no reused edge.
3. **Portable multi-hop Cypher.** HydraDB and Kuzu both store SelfGraph relations as one edge label with
   `etype`/`is_current`/`revision`, but the labels differ (`RELATES`/`Entity` vs `R`/`N`). A small
   `store.dialect` (or a typed `graph.traverse(meta_path, start)` method) would let add-ons avoid physical-layout
   knowledge in `run_cypher`.
4. **Change events.** A subscription hook on supersede (`graph.on_relation_retired(callback)`) would replace
   polling `relations.get()` during revalidation.

## Measured effect (this repo, `make eval`)

See [`results/results.md`](../results/results.md). On held-out questions about unseen entities, after learning
rounds, agent C answers with fewer LLM calls and tokens per task than the same agent without routes, at the same
accuracy. The heal test (`results/heal.json`) shows a one-fact change retiring dependent templates, rebuilding them
as v2, and answers staying correct while a stale-route agent returns the superseded fact.

## Scope / non-goals

- Routes are learned per question *shape* (the masked question text). Clustering paraphrases is left to the caller.
  The router in the reference agent is one LLM call.
- No change to SelfGraph's storage format.
