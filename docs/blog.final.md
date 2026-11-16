# Desire Paths: teaching a knowledge graph the routes its agents keep walking

*Built in one night for the HydraDB hackathon on [HydraDB](https://github.com/hydra-db/hydradb) (the open-source engine,
self-hosted) and [SelfGraph](https://github.com/hydra-db/selfgraph). Code: https://github.com/Jmohak2004/desire-paths*

## The problem

Ask an agent "who is on call for the team that owns the project Ana works on?" and it walks a graph: find Ana,
look at her project, look at the owning team, look at its on-call person. Each hop is an LLM call. Ask the same
*kind* of question about Ben tomorrow and the agent walks the same hops again and pays again. Nothing it learned
yesterday made today cheaper.

A desire path is the trail worn into grass by people taking the route the pavement should have taken. Desire Paths
does that for a graph. It watches which typed paths the agent walks when it gets answers right, and turns the
frequent ones into **route templates** that run as **one graph query**.

## How it works

1. **Log the walk, keep the types.** A successful answer becomes a trace: the typed path the agent crossed, such as
   `(Person)-[WORKS_ON]->()-[OWNED_BY]->()-[ON_CALL]->()`, plus the relation ids and versions it used.
2. **Verify, then promote.** Each candidate path is executed as a single query from the question's entity. It must
   return exactly the agent's answer. A path is promoted once it explains at least 80% of a question shape's
   successful traces, with support ≥ 3.
3. **Answer new questions in one query.** A question about an entity never seen before matches a learned route,
   either through its masked shape (zero LLM calls) or through a one-call router. HydraDB then runs the whole route
   as one Cypher query over current facts.
4. **Heal when facts change.** Each route stores provenance: the relation ids and revisions behind its support.
   When SelfGraph supersedes a fact, every route that depends on it retires, re-binds to the current graph, and
   comes back as v2.

## Results (measured, held-out, 3 seeds)

Model `gemma-4-26b-a4b-it` (temperature 0) for every agent; backend **hydradb**; seeds [0, 1, 2].

| | accuracy | accuracy within 1 LLM call | LLM calls / task | tokens / task |
|---|---|---|---|---|
| A · vector RAG | 0.71 | 0.02 | 2.52 | 733 |
| B · graph agent | 0.99 | 0.00 | 4.87 | 3195 |
| C · Desire Paths (after 4 rounds) | 1.00 | 0.95 | 0.54 | 326 |

C's accuracy within one LLM call, by learning round: 0.00 → 0.28 → 0.83 → 0.95 → 0.95.

## The technical problems, and how we solved them

**1. The shortest explanation is often the wrong one.** "Who is on call for the owning team?" has an equally short
wrong path: "any member of that team" also reaches the on-call person. Fix: verify every candidate meta-path by
executing it, and keep only paths that return exactly the answer.

**2. Coincidences survive verification.** In one trace the PR author *was* the team manager, so a 2-hop path explained
a 4-hop question perfectly. One trace can't tell them apart. Fix: attach a path to a question shape only if it
explains ≥80% of that shape's traces; among equals, the shortest wins.

**3. Real routes are walks, not simple paths.** Author → team → manager can come back to the same person, so
enumerating simple paths misses the true route. Fix: bounded walks that may revisit an entity but never reuse an edge.

**4. HydraDB's physical layout.** SelfGraph stores entities in HydraDB under integer surrogate ids, with the string
ids on the edges (`fa`/`tb`). `MATCH (n:Entity {id: 'person:1'})` fails with "node id property must be an
integer". Fix: a small dialect that seeks by the surrogate id and reads answers from the edges, so one learned
route compiles to one query on both HydraDB and embedded Kuzu.

**5. Router mistakes poisoned learning.** Early on, a router error (the right entity sent to the wrong route) counted
against a *correct* route and demoted it. Fix: log router errors as misroutes; only a wrong answer from the
shape index counts against a route. We also added an entity check: the resolved start entity must be the right
type *and* be named in the question.

**6. Our latency number was wrong, and we caught it.** Scoring 36 questions concurrently made each question's graph
time include waiting behind the other 35. Fix: score held-out questions sequentially. Latency is now measured LLM
time plus measured graph time.

**7. The model we planned on didn't answer.** Gemma 4 on one hosted API took 112–200 s per call or timed out. We
measured the alternatives on the real agent task, ran the full eval on the best working model, then switched to
Gemma 4 on the Gemini API once a key was available and re-ran everything. Both runs are in the repo.

**8. A thinking model ate its own answer.** Gemma 4 writes a `<thought>` block before it replies. Our router call
allowed 120 output tokens, so the thought used them all and the reply came back empty: every new phrasing fell back
to the expensive walk. We found it by counting empty replies in the request cache (165 of them), confirmed it with
`finish_reason=length`, and gave every call from every agent the same 1,500-token cap before re-running.

## Why it needs a graph

The vector-RAG baseline, iterative and with the same LLM, reaches only 0.71 accuracy: a multi-hop answer's
facts don't *look like* the question. The learned route needs typed relations to generalise to any entity, one-query
multi-hop execution to skip the per-hop LLM calls, and versioned facts to know when it is stale. A plain store has
none of these.

## Try it

Live demo: https://denver-spokesman-music-wall.trycloudflare.com · Code: https://github.com/Jmohak2004/desire-paths · `make demo`
