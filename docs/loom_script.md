# Loom walkthrough (about 4 minutes)

Before recording: `make demo` (fresh HydraDB node + dashboard). Open the live link and the GitHub repo in two tabs.

## 0:00–0:30 · The problem and the pitch
On screen: dashboard header.
> "I'm Mohak. This is Desire Paths, a context layer on HydraDB, the open-source graph engine, running locally, built
> from source. Agents that answer multi-hop questions walk the graph hop by hop and pay one LLM call per hop, every
> time. Desire Paths learns the routes they keep walking, so the graph gets sharper and cheaper the more it's used.
> Track 1, a self-improving graph: this is path compression learned from the agent's own answers."

## 0:30–1:20 · The metric that matters, and the baseline
On screen: the "Accuracy rises with use" chart, then the held-out table.
> "The metric: on held-out questions about entities the system never saw in training, how many does it answer
> correctly within a budget of one LLM call? The baseline graph agent, B, needs about five calls, so it scores zero.
> Vector RAG, A, can't do multi-hop. Desire Paths, C, starts at zero and rises every round as it learns routes from
> its own successful walks. Unconstrained accuracy stays the same as B's, while LLM calls and tokens per task fall."
Point at: 3 seeds, mean ± std, model and backend in the footnote.

## 1:20–2:10 · Live: the same question, B vs C
On screen: Ask box. Click a held-out example (not ✦), then **B**, then **C**.
> "Here's a held-out question. B walks the graph: about five LLM calls, 20–40 seconds with Gemma 4. C recognises the question shape,
> picks the learned route and runs it as one HydraDB query: zero LLM calls, well under a second, same answer. Here's the
> path it took and the relation versions it used."
Click a ✦ question: "A phrasing it has never seen goes through a one-call router. Gemma thinks before answering, so this
> call takes 15–30 seconds; it's still one call instead of five."
Optional: route library → **show the one-query Cypher**.

## 2:10–3:00 · Live: heal
On screen: **Change one fact** → click the suggested question → **Ask C** → **Rebuild** → **Ask C**.
> "Facts change. I'll change one team's on-call person. SelfGraph versions the relation, and every route whose
> provenance used the old version retires. C still answers correctly by walking. Rebuild re-binds the route to
> current facts as version 2, and it's back to one query. In the recorded test, a stale-route agent that replays pinned
> relation ids returns the old person."

## 3:00–3:40 · Why it needs the graph, and does it hold up
> "Why not a vector store? The answer's facts don't look like the question, and A shows it. Routes need typed
> relations to generalise, one-query multi-hop execution, and versioned facts. Under load, learned routes on
> HydraDB ..." (read the load-test line from `results/loadtest.md`).

## 3:40–4:00 · Go-to-market
On screen: savings calculator; type their volume.
> "Every number is measured. Type your monthly task volume and price: this is your cost per thousand tasks.
> Agent cost per task falls as your graph is used. Code, results and `make eval` to reproduce are on GitHub."
