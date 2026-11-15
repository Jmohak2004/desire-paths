"""Desire Paths dashboard: live agent C over a real SelfGraph graph, plus the measured eval results.

    make dashboard            # http://127.0.0.1:8000

Live endpoints run the real agents (LLM + graph); nothing is replayed except LLM responses already in the
request cache. Measured endpoints read results/ written by `make eval`.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from bench.gen import QTEMPLATES, generate, make_questions
from desirepaths.agents import DesirePaths, GraphAgent, correct
from desirepaths.backend import GraphBackend, hydradb_settings, make_selfgraph, selfgraph_schema
from desirepaths.llm import LLM, MODEL
from desirepaths.routes import RouteLibrary, describe

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SEED = 0
STATE: dict = {}


async def boot() -> None:
    g = generate(SEED)
    train, test = make_questions(g, 8, 6, SEED)
    sg, dialect, ns = make_selfgraph(str(RESULTS / "graphs" / "dash_seed0.kuzu"), selfgraph_schema(), fresh=True, namespace="dash0")
    await sg.__aenter__()
    backend = GraphBackend(sg, dialect, namespace=ns)
    t0 = time.time()
    await backend.load(g)
    routes_path = RESULTS / f"routes_seed{SEED}.json"
    lib = RouteLibrary.load(str(routes_path)) if routes_path.exists() else RouteLibrary()
    # The saved library's provenance points at relation ids from the eval's graph load. Ids are derived
    # deterministically by SelfGraph from (from, type, to), so they match this fresh load of the same seed.
    llm = LLM()
    B = GraphAgent(llm)
    C = DesirePaths(llm, lib, B)
    C.learning = False
    STATE.update(g=g, train=train, test=test, sg=sg, backend=backend, lib=lib, llm=llm, B=B, C=C,
                 dialect=dialect.name, load_s=round(time.time() - t0, 1), events=[], lock=asyncio.Lock(),
                 extra_gold={})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await boot()
    yield
    await STATE["sg"].__aexit__(None, None, None)


app = FastAPI(title="Desire Paths", lifespan=lifespan)


def _read(name: str):
    p = RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/status")
def status():
    b = STATE["backend"]
    return {"model": MODEL, "backend": STATE["dialect"], "hydradb_configured": bool(hydradb_settings()),
            "nodes": len(STATE["g"].nodes), "edges": len(STATE["g"].edges), "graph_load_s": STATE["load_s"],
            "graph_calls_total": b.calls, "active_routes": len(STATE["lib"].active())}


@app.get("/api/results")
def results():
    return {"summary": _read("summary.json"), "savings": _read("savings.json"), "heal": _read("heal.json"),
            "probe": (RESULTS / "model_probe.md").read_text() if (RESULTS / "model_probe.md").exists() else None}


@app.get("/api/routes")
def routes():
    lib: RouteLibrary = STATE["lib"]
    g = STATE["g"]
    out = []
    for rt in sorted(lib.templates.values(), key=lambda r: (r.status != "active", r.id)):
        if rt.status == "candidate" and not rt.events:
            continue  # unpromoted hypotheses: shown as a count only
        out.append({"id": rt.id, "status": rt.status, "version": rt.version, "signature": rt.signature(),
                    "hops": rt.hops, "start_type": rt.start_type, "support": len(rt.support),
                    "depends_on": len(rt.depends_on()), "exemplars": rt.exemplars, "uses": rt.uses,
                    "events": rt.events})
    hyp = sum(1 for r in lib.templates.values() if r.status == "candidate" and not r.events)
    return {"routes": out, "unpromoted_hypotheses": hyp}


@app.get("/api/examples")
def examples():
    test = STATE["test"]
    seen, out = set(), []
    for q in test:
        if q.template not in seen:
            seen.add(q.template)
            out.append({"question": q.text, "gold": q.gold_names, "template": q.template})
    return out


class Ask(BaseModel):
    question: str
    agent: str = "C"


@app.post("/api/ask")
async def ask(req: Ask):
    if not req.question.strip():
        raise HTTPException(400, "empty question")
    b = STATE["backend"]
    gold = STATE["extra_gold"].get(req.question) or next(
        (q.gold_names for q in STATE["test"] + STATE["train"] if q.text == req.question), None)
    t0 = time.perf_counter()
    if req.agent == "B":
        res = await STATE["B"].answer(req.question, b)
    else:
        res = await STATE["C"].answer(req.question, b)
    wall = time.perf_counter() - t0
    path = []
    for s in res.steps:
        if "provenance" in s:
            rt = STATE["lib"].get(s["route"])
            nodes = [s["start"]]
            cur = s["start"]
            for (rid, rev), (rel, d) in zip(s["provenance"], rt.hops):
                r = await b.sg.relations.get(rid)
                nxt = r.to_entity if d == "out" else r.from_entity
                path.append({"from": b.name(cur), "from_type": b.etype(cur), "rel": rel, "dir": d, "rel_id": rid,
                             "revision": rev, "to": b.name(nxt), "to_type": b.etype(nxt)})
                cur = nxt
                nodes.append(nxt)
    return {"agent": req.agent, "answer": res.answer, "gold": gold, "correct": correct(res.answer, gold) if gold else None,
            "route": res.route, "fallback": res.fallback, "path": path, "metrics": res.metrics(),
            "wall_s": round(wall, 2), "steps": res.steps[-12:]}


@app.post("/api/mutate")
async def mutate():
    """Change ONE fact a learned route depends on: a team's on-call person. Retires dependent templates."""
    async with STATE["lock"]:
        g, b, lib = STATE["g"], STATE["backend"], STATE["lib"]
        hops = [tuple(h) for h in QTEMPLATES["oncall_for_person_project"]["hops"]]
        rt = next((t for t in lib.templates.values() if t.hops == hops and t.support), None)
        if rt is None:
            raise HTTPException(409, "no on-call route learned yet")
        rel_id = rt.support[0].provenance[-1][0]
        r = await b.sg.relations.get(rel_id)
        if r is None or not r.is_current:
            # already changed once: use the current on-call relation of the same team
            cur = await b.sg.relations.list(from_entity=r.from_entity if r else "", type="ON_CALL")
            r = cur.items[0]
        team, old = r.from_entity, r.to_entity
        members = [p for p in g.inn(team, "MEMBER_OF") if p != old]
        new = members[len(STATE["events"]) % len(members)]
        retired_rel, new_rel = await b.supersede(team, "ON_CALL", new)
        retired = lib.on_relation_change(retired_rel, reason="ON_CALL superseded (dashboard)")
        train_starts = {x.start for x in STATE["train"]}
        person = next((p for p in g.nodes if p.startswith("person:") and p not in train_starts
                       and [x for x in g.out(p, "WORKS_ON") if team in g.out(x, "OWNED_BY")]), None)
        # a phrasing seen in training, about a person never seen in training
        q = QTEMPLATES["oncall_for_person_project"]["phrasings"][0].format(x=g.nodes[person].name) if person else None
        ev = {"fact": f"{b.name(team)} ON_CALL: {b.name(old)} -> {b.name(new)}", "retired_relation": retired_rel,
              "new_relation": new_rel, "retired_templates": [t.id for t in retired], "try_question": q,
              "expected_answer": b.name(new)}
        STATE["events"].append(ev)
        if q:
            STATE["extra_gold"][q] = [b.name(new)]  # gold for the suggested question follows the changed fact
        # keep the generator graph in sync so gold answers stay correct for the try-question
        for e in g.edges:
            if e.src == team and e.type == "ON_CALL":
                e.dst = new
        g.index()
        return ev


@app.post("/api/revalidate")
async def revalidate():
    async with STATE["lock"]:
        rebuilt = await STATE["lib"].revalidate(STATE["backend"])
        return {"rebuilt": [{"id": t.id, "version": t.version, "support": len(t.support)} for t in rebuilt]}


@app.get("/api/route_example/{rid}")
async def route_example(rid: str):
    lib, b = STATE["lib"], STATE["backend"]
    rt = lib.get(rid)
    if rt is None or not rt.support:
        raise HTTPException(404, "unknown route")
    rows = await b.run_route(rt.hops, rt.support[0].start)
    return {"route": rid, "cypher": b.compile_route(rt.hops), "signature": describe(rt.start_type, rt.hops),
            "start": b.name(rt.support[0].start), "answers": [b.name(r["answer"]) for r in rows]}
