# Social posts (HydraDB on X: @hydra_db, from the hydra-db GitHub organisation profile)

## X thread

1/ Agents answering multi-hop questions pay one LLM call per hop, every time, even for questions they've answered
100 times.

I built Desire Paths at the @hydra_db hackathon: a graph that learns the routes its agents keep walking, so it gets
cheaper and sharper with use. 🧵

2/ How: every successful walk is logged as a typed path, for example Person→Project→Team→On-call. Paths that keep
explaining correct answers get promoted to route templates.

A NEW question about an entity it has never seen runs the route as ONE HydraDB query.

3/ The metric: held-out questions answered correctly within 1 LLM call.
Graph agent baseline: {{B1}}
Vector RAG: {{A1}}
Desire Paths: {{C1_START}} → {{C1_END}} as it learns, over {{ROUNDS}} rounds, 3 seeds.

Unconstrained accuracy holds at {{C_ACC}}, with {{CUT}} fewer LLM calls per task.

4/ Facts change. Every route stores provenance (relation ids and versions). Change one fact and the dependent
routes retire, rebuild as v2, and answers stay right, while a stale-route agent returns the old answer.

5/ Built on the open-source HydraDB engine (self-hosted, from source) and SelfGraph. Everything is measured and
reproducible with `make eval`.

Live: {{LIVE}}
Code: https://github.com/Jmohak2004/desire-paths

## LinkedIn

I spent the night at the HydraDB hackathon building **Desire Paths**: a knowledge-graph layer that makes AI agents
cheaper the more they're used.

AI agents answer multi-hop questions ("who's on call for the team that owns Ana's project?") by walking a graph one
LLM call per hop, and they repeat that cost every time. Desire Paths watches which typed paths lead to correct
answers and compiles them into route templates. A new question, even about an entity it has never seen, then runs
as a single graph query.

What we measured (held-out questions, 3 seeds):
• Accuracy within a 1-LLM-call budget rose from {{C1_START}} to {{C1_END}} as the system learned. The baseline
  graph agent scores {{B1}} under the same budget.
• {{CUT}} fewer LLM calls per task at the same accuracy ({{C_ACC}}).
• When a fact changes, the dependent routes retire and rebuild automatically, so answers stay correct.

Who pays for this: any team running agents over company knowledge (on-call routing, incident triage, org and
ownership questions) where the same question shapes repeat thousands of times a day. Agent cost per task falls as
your graph is used.

Built on the open-source HydraDB engine and SelfGraph. Live demo: {{LIVE}} · Code:
https://github.com/Jmohak2004/desire-paths

#HydraDB #AIagents #knowledgegraph #LLM
