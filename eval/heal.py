"""Heal test: mutate one fact, watch dependent route templates retire and rebuild, check answers stay correct.

1. Learn routes on the seed's TRAIN questions (live agent C, gold decides success).
2. Pick a promoted on-call template and one ON_CALL relation in its provenance (team X -> person P_old).
3. Ask a question whose answer runs through team X, using an entity never seen in train:
     C (Desire Paths)          -> P_old, via the route
     Stale-route agent          -> P_old, and it records the exact relation ids it crossed
4. Mutate ONE fact through SelfGraph: team X's on-call becomes P_new. SelfGraph retires the old relation version.
   The change event retires every template whose provenance contains it.
5. Ask again: C falls back to the graph walk while its template is retired (still correct, costs more);
   revalidation re-binds the template's support to current facts and re-promotes it as a new version;
   C then answers through the rebuilt route (1 LLM call). The stale-route agent replays its recorded relation ids
   and returns P_old: wrong.
Writes results/heal.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from bench.gen import QTEMPLATES, generate, make_questions, walk
from desirepaths.agents import QB, DesirePaths, GraphAgent, correct
from desirepaths.backend import GraphBackend, make_selfgraph, selfgraph_schema
from desirepaths.llm import LLM, MODEL, Meter, parse_json
from desirepaths.agents import ROUTER
from desirepaths.routes import RouteLibrary

RESULTS = Path(__file__).resolve().parent.parent / "results"


class StaleRouteAgent:
    """Learns the same routes, but stores each resolved route as its concrete relation ids and replays them.

    This is what a route cache without versioned provenance does: it reads the graph live, but along pinned
    relation ids, so it never notices that a fact was superseded.
    """

    def __init__(self, llm: LLM, desire: DesirePaths):
        self.llm, self.c = llm, desire
        self.pinned: dict[tuple[str, str], list[str]] = {}

    async def answer(self, question: str, backend) -> dict:
        meter = Meter()
        qb = QB(backend)
        out = parse_json(await self.llm.chat(
            [{"role": "user", "content": ROUTER.format(routes=self.c.route_menu(), question=question)}],
            meter, max_tokens=120, tag="C.router"))
        rid = str(out.get("route", ""))
        rt = self.c.lib.get(rid)
        hits = await qb.search(str(out.get("entity", ""))[:200])
        start = next((h for h in hits if rt and h["type"] == rt.start_type), None)
        if rt is None or start is None:
            return {"answer": [], "llm_calls": meter.calls, "note": "no route"}
        key = (rid, start["id"])
        if key not in self.pinned:
            rows = await qb.run_route(rt.hops, start["id"])
            self.pinned[key] = [sid for sid, _ in rows[0]["provenance"]]
        last = await backend.sg.relations.versions(self.pinned[key][-1])  # replay the pinned relation id
        ans = last[0].to_entity if last else ""  # newest version of the PINNED id (may be retired)
        return {"answer": [backend.name(ans)], "llm_calls": meter.calls, "pinned": self.pinned[key]}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--train-per-template", type=int, default=8)
    ap.add_argument("--test-per-template", type=int, default=6)
    args = ap.parse_args()
    seed = args.seed
    g = generate(seed)
    train, test = make_questions(g, args.train_per_template, args.test_per_template, seed)
    path = str(RESULTS / "graphs" / f"heal_seed{seed}.kuzu")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sg, dialect, ns = make_selfgraph(path, selfgraph_schema(), fresh=True, namespace=f"heal{seed}")
    timeline: list[dict] = []

    def log(event, **kw):
        kw = {"t": round(time.time() - t0, 2), "event": event, **kw}
        timeline.append(kw)
        print(json.dumps(kw), flush=True)

    t0 = time.time()
    async with sg:
        backend = GraphBackend(sg, dialect, namespace=ns)
        await backend.load(g)
        llm = LLM()
        lib = RouteLibrary(min_support=3)
        C = DesirePaths(llm, lib, GraphAgent(llm))
        stale = StaleRouteAgent(llm, C)

        # 1. learn on train
        for i in range(0, len(train), 12):
            batch = train[i:i + 12]
            await asyncio.gather(*[C.answer(q.text, backend, gold_names=q.gold_names) for q in batch])
            lib.clock += 1
            lib.promote()
        C.learning = False
        log("learned", active=[(t.id, t.signature(), t.version) for t in lib.active()])

        # 2. pick a template + an ON_CALL relation in its provenance
        oncall_hops = [tuple(h) for h in QTEMPLATES["oncall_for_person_project"]["hops"]]
        rt = next((t for t in lib.active() if t.hops == oncall_hops), None)
        if rt is None:
            raise SystemExit("on-call template was not learned; heal test cannot run (see results/routes_seed*.json)")
        train_starts = {q.start for q in train}
        choice = None
        for s in rt.support:
            team = walk(g, s.start, oncall_hops[:2])[0][0]
            old_rel = s.provenance[-1][0]
            # a NEW person (not a train start) whose project is owned by this team
            people = [p for p in g.nodes if p.startswith("person:") and p not in train_starts
                      and walk(g, p, oncall_hops[:2])[0] == [team]]
            if people:
                choice = (team, old_rel, people[0])
                break
        if choice is None:
            raise SystemExit("no unseen entity routes through a provenance team; increase graph size")
        team, old_rel, person = choice
        p_old = g.out(team, "ON_CALL")[0]
        p_new = next(p for p in g.inn(team, "MEMBER_OF") if p != p_old)
        qtext = QTEMPLATES["oncall_for_person_project"]["phrasings"][2].format(x=g.nodes[person].name)
        log("scenario", template=rt.id, version=rt.version, team=g.nodes[team].name, relation=old_rel,
            question=qtext, on_call_before=g.nodes[p_old].name, on_call_after=g.nodes[p_new].name,
            dependents=[t.id for t in lib.active() if old_rel in t.depends_on()])

        async def ask(phase, gold):
            r = await C.answer(qtext, backend)
            s = await stale.answer(qtext, backend)
            log(f"ask:{phase}", gold=gold,
                desire={"answer": r.answer, "correct": correct(r.answer, [gold]), "route": r.route,
                        "fallback": r.fallback, "llm_calls": r.meter.calls, "graph_calls": r.graph_calls},
                stale={"answer": s["answer"], "correct": correct(s["answer"], [gold]), "llm_calls": s["llm_calls"]})

        # 3. before
        await ask("before_change", g.nodes[p_old].name)

        # 4. mutate one fact via SelfGraph's versioned API
        retired_rel, new_rel = await backend.supersede(team, "ON_CALL", p_new)
        cur, _ = await backend.relation_state(retired_rel)
        log("fact_changed", retired=retired_rel, new=new_rel, retired_is_current=cur,
            fact=f"{g.nodes[team].name} ON_CALL {g.nodes[p_old].name} -> {g.nodes[p_new].name}")
        retired = lib.on_relation_change(retired_rel, reason="ON_CALL superseded")
        log("templates_retired", ids=[(t.id, t.signature(), t.version) for t in retired])

        # 5a. while retired: C falls back to walking the graph
        await ask("after_change_template_retired", g.nodes[p_new].name)
        # 5b. revalidate -> rebuilt version
        rebuilt = await lib.revalidate(backend)
        log("templates_rebuilt", ids=[(t.id, t.version, len(t.support)) for t in rebuilt],
            still_depends_on_retired=[t.id for t in rebuilt if retired_rel in t.depends_on()])
        # 5c. after rebuild
        await ask("after_rebuild", g.nodes[p_new].name)
        lib.save(str(RESULTS / f"routes_heal_seed{seed}.json"))
    out = {"model": MODEL, "seed": seed, "backend": dialect.name, "timeline": timeline}
    (RESULTS / "heal.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
