# STATUS

_Updated: 2026-11-16 ~12:00 IST_

## Submission checklist (hackathon deadline 5 PM IST; tracks and Bounty #2 by 11 PM IST)
- [x] Public repo: https://github.com/Jmohak2004/desire-paths (CI green)
- [x] Live link: https://denver-spokesman-music-wall.trycloudflare.com (Cloudflare quick tunnel to the dashboard on
      this Mac; the Mac must stay on, plugged in and online. If cloudflared restarts the URL changes; see `scratch/tunnel.log`)
- [x] Always-up read-only snapshot: https://jmohak2004.github.io/desire-paths/ (GitHub Pages; rebuild with `make site`,
      then push `site/` to the gh-pages branch)
- [x] Go-to-market section (README + dashboard): who pays, measured economics, pricing hypothesis, honest status
- [ ] Loom (about 4 min): script in `docs/loom_script.md`; record after `make demo`
- [ ] Posts tagging HydraDB on X and LinkedIn: drafts in `docs/social_posts.md`
- [ ] Submit live link + repo + Loom: https://forms.gle/9brHhy7BC229tw868
- [ ] Bounty #2 (article on X + tweet): draft in `docs/blog.md`; submit https://forms.gle/i8ybFDVciMThjhGbA
- Bounty #1 (SelfGraph issue + PR): DONE. Issue https://github.com/hydra-db/selfgraph/issues/165 was approved by a
  maintainer, and PR https://github.com/hydra-db/selfgraph/pull/175 was approved and MERGED (2026-11-16 09:09 UTC).
  Fix: connection errnos are matched by number, not by platform name, so Windows gets "connection refused" and the
  test passes on macOS and Windows. Upstream CI was 16/16 green on the final commit.

## Works (verified)
- **HydraDB v0.4.0**, built from source and running locally (`make hydradb`; Bolt 7687; telemetry off).
  `make gate` passes: SelfGraph typed insert, learned route as one Cypher query, versioned supersede,
  neighbors, raw Bolt Cypher fallback (`results/gate_hydradb.json`).
- `make test`: 9 passed against live HydraDB in 22 s on a fresh store.
- `make eval`: full pipeline on HydraDB. 3 seeds × 4 rounds, 48 train / 36 held-out questions per seed, then the
  heal test, savings calculator and README update. Re-running it from the request cache reproduced A, B and
  seed 0 exactly (see run-to-run note in the README).
- Final run (Gemma 4 `gemma-4-26b-a4b-it`, self-hosted HydraDB, 3 seeds, held-out questions): accuracy within one
  LLM call 0.00 → 0.28 → 0.83 → 0.95 over 4 rounds (B 0.00, A 0.02). Unconstrained accuracy C 1.00, B 0.99, A 0.71.
  LLM calls per task 0.54 vs 4.87 (89% fewer); tokens per correct answer 326 vs 3,226. First full run (laguna)
  archived in `results/archive/`, with the same conclusions.
- Load test on HydraDB (`results/loadtest.md`): 360/360 correct at concurrency 1–64, zero errors. Routes give
  higher throughput and a lower median than hop-by-hop walking, but a worse p95 tail at high concurrency.
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
