# X posts (copy and paste)

HydraDB on X: **@hydra_db** (from the hydra-db GitHub organisation profile).
Every number comes from `results/` (Gemma 4, self-hosted HydraDB, 3 seeds, held-out questions).

Links:
- Write-up (blog): https://jmohak2004.github.io/desire-paths/blog/
- Live demo: https://desire-paths-qhfa.onrender.com
- Always-up snapshot: https://jmohak2004.github.io/desire-paths/
- Code: https://github.com/Jmohak2004/desire-paths

---

## 1. Bounty #2: the write-up tweet

If you have X Premium, also paste `docs/blog.final.md` into an X Article and link that instead of the blog. Submit
the article or blog link plus this tweet's link in the Bounty #2 form.

> I wrote up how I built Desire Paths at the @hydra_db hackathon: a graph that learns the routes its agents keep walking.
>
> Self-hosted HydraDB + SelfGraph. 89% fewer LLM calls at equal accuracy; routes heal when facts change.
>
> What broke, and the fixes 👇
> https://jmohak2004.github.io/desire-paths/blog/

Attach: `docs/img/curve.png` (the rising accuracy curve).

---

## 2. Hackathon launch thread (go-to-market)

**1/**
> AI agents answering multi-hop questions pay one LLM call per hop, every time, even for questions they've answered a hundred times.
>
> At the @hydra_db hackathon I built Desire Paths: a graph that learns the routes its agents keep walking, so it gets cheaper with use 🧵

Attach: `docs/demo.mp4` (71 s, under X's 2:20 limit).

**2/**
> Every correct walk is logged as a typed path, like Person → Project → Team → On-call.
>
> Paths that keep explaining correct answers become route templates. A question about an entity it has never seen then runs as ONE HydraDB query.

**3/**
> The metric: held-out questions answered correctly within 1 LLM call.
>
> Graph agent: 0.00
> Desire Paths: 0.00 → 0.28 → 0.83 → 0.95 over 4 learning rounds
>
> Same accuracy as the full walk (1.00 vs 0.99), with 89% fewer LLM calls. 3 seeds.

Attach: `docs/img/curve.png`.

**4/**
> Facts change, so every route keeps provenance: the relation ids and versions it was learned from.
>
> Change one on-call person and the route retires, rebuilds as v2, and stays right. A route cache that pins old ids returns the old person.

Attach: `docs/img/after_rebuild.png`.

**5/**
> Who pays: teams running agents over company knowledge (on-call, incident routing, helpdesks).
>
> Measured at Sonnet list prices: $6.92 → $0.72 per 1,000 tasks.
>
> Built on the open-source HydraDB engine, self-hosted.
> Live: https://desire-paths-qhfa.onrender.com
> Code: https://github.com/Jmohak2004/desire-paths

---

## 3. LinkedIn

Use `docs/social_posts.final.md` (LinkedIn section). Tag HydraDB's LinkedIn page by typing "@HydraDB" and picking
it from the suggestions.
