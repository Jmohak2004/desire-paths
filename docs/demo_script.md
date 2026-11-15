# 60-second demo script

Setup, before you record: `make hydradb` (terminal 1), `make dashboard` (terminal 2), then open http://127.0.0.1:8000.
Backup recording: `docs/demo.mp4`, made with `make record` from the live dashboard.

| time | on screen | say |
|---|---|---|
| 0:00–0:08 | Header, KPI tiles | "Agents answer multi-hop questions by walking a graph, and they pay an LLM call for every hop, every time. Desire Paths makes that cost fall the more the graph is used." |
| 0:08–0:18 | The two learning-curve charts | "Each successful walk is logged as a typed path, such as Person → Project → Team → On-call. Once a path has enough support, it is promoted to a route template. Over rounds, C's LLM calls and tokens per question drop, while vector RAG and the plain graph agent stay flat." |
| 0:18–0:32 | Ask box: pick a held-out example, click **B**, then **C** | "This is a held-out question about an entity the system never saw in training, so it can't be a cache. B walks the graph in about five LLM calls. C matches the question to a learned route and runs it as one HydraDB query: one LLM call, same answer. Here is the path and the relation versions it used." |
| 0:32–0:48 | **Change one fact**, click the suggested question, **Ask C**, **Rebuild**, **Ask C** | "Now change one fact: a team's on-call person. SelfGraph versions it, and every route whose provenance contains the old relation retires. C still answers correctly by walking the graph while the route is down. Rebuild re-binds the route to current facts as version 2, and it's back to one call. A stale-route agent that replays pinned relation ids returns the old on-call person." |
| 0:48–0:60 | Savings calculator: set volume to 1,000,000 | "Every number here is measured on held-out questions over three seeds. At your volume and your prices, this is the cost per thousand tasks for each approach. Agent cost per task falls as your graph is used." |
