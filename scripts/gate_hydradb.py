"""GATE: prove we can write custom nodes/edges and run Cypher on HydraDB.

Needs HYDRADB_URI (bolt://host:port) and HYDRADB_TOKEN (in env or .env). Runs three checks:
  1. SelfGraph HydraDBStore: typed insert of entities + a versioned relation, then supersede it.
  2. SelfGraph run_cypher: compile a learned route template to Cypher and execute it as ONE query.
  3. Direct Cypher fallback over the neo4j Bolt driver (no SelfGraph): CREATE + MATCH custom nodes/edges.
Writes results/gate_hydradb.json. Exit code 0 only if every check passed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from desirepaths import llm as _env  # noqa: F401,E402  (loads .env)
from desirepaths.backend import HYDRADB, GraphBackend, hydradb_settings, make_selfgraph  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "results" / "gate_hydradb.json"


async def main() -> int:
    hs = hydradb_settings()
    report: dict = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "uri_set": bool(hs), "checks": {}}
    if not hs:
        report["error"] = "HYDRADB_URI not set; nothing to test"
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(report, indent=1))
        print(report["error"])
        return 2
    ns = f"gate-{uuid.uuid4().hex[:6]}"
    schema = {"entities": [{"name": "Person"}, {"name": "Team"}, {"name": "Project"}],
              "relations": [{"type": "WORKS_ON", "from": {"types": ["Person"], "max_count": 1}, "to": {"types": ["Project"]}},
                            {"type": "OWNED_BY", "from": {"types": ["Project"], "max_count": 1}, "to": {"types": ["Team"]}},
                            {"type": "ON_CALL", "from": {"types": ["Team"], "max_count": 1}, "to": {"types": ["Person"]}}]}
    try:
        sg, d = make_selfgraph("", schema, fresh=False, namespace=ns)
        assert d is HYDRADB
        async with sg:
            b = GraphBackend(sg, d, namespace=ns)
            await sg.insert.facts({"entities": [
                {"id": "person:a", "type": "Person", "name": "Gate Alice"}, {"id": "person:b", "type": "Person", "name": "Gate Bob"},
                {"id": "person:c", "type": "Person", "name": "Gate Cara"}, {"id": "project:x", "type": "Project", "name": "Gate X"},
                {"id": "team:t", "type": "Team", "name": "Gate Team"}],
                "relations": [{"from_entity": "person:a", "type": "WORKS_ON", "to_entity": "project:x"},
                              {"from_entity": "project:x", "type": "OWNED_BY", "to_entity": "team:t"},
                              {"from_entity": "team:t", "type": "ON_CALL", "to_entity": "person:b"}]})
            for n in ("person:a", "person:b", "person:c", "project:x", "team:t"):
                b._names[n] = (n, n.split(":")[0].title())
            report["checks"]["selfgraph_insert"] = "ok"
            hops = [("WORKS_ON", "out"), ("OWNED_BY", "out"), ("ON_CALL", "out")]
            report["route_cypher"] = b.compile_route(hops)
            rows = await b.run_route(hops, "person:a")
            assert [r["answer"] for r in rows] == ["person:b"], rows
            report["checks"]["route_single_query"] = {"answer": rows[0]["answer"], "provenance": rows[0]["provenance"]}
            old, new = await b.supersede("team:t", "ON_CALL", "person:c")
            cur, rev = await b.relation_state(old)
            rows2 = await b.run_route(hops, "person:a")
            assert not cur and [r["answer"] for r in rows2] == ["person:c"], (cur, rows2)
            report["checks"]["versioned_supersede"] = {"retired": old, "new": new, "answer_after": rows2[0]["answer"]}
            nb = await b.neighbors("team:t")
            report["checks"]["neighbors"] = [(n.rel_type, n.direction, n.id) for n in nb]
    except Exception as e:  # report, then still try the raw fallback
        report["checks"]["selfgraph_error"] = f"{type(e).__name__}: {e}"[:800]
    try:
        from neo4j import AsyncGraphDatabase

        drv = AsyncGraphDatabase.driver(hs[0], auth=("neo4j", hs[1]) if hs[1] else None)
        async with drv.session(database=os.environ.get("HYDRADB_DATABASE") or "default") as s:
            tag = uuid.uuid4().hex[:8]
            await s.run("CREATE (a:DPGate {k: $k, role: 'person'})-[:DP_ROUTE {kind: 'test'}]->(b:DPGate {k: $k, role: 'team'})", k=tag)
            res = await s.run("MATCH (a:DPGate {k: $k})-[r:DP_ROUTE]->(b:DPGate) RETURN a.role AS a, r.kind AS r, b.role AS b", k=tag)
            data = [dict(r) async for r in res]
            assert data == [{"a": "person", "r": "test", "b": "team"}], data
            report["checks"]["raw_cypher_fallback"] = data
        await drv.close()
    except Exception as e:
        report["checks"]["raw_cypher_error"] = f"{type(e).__name__}: {e}"[:800]
    ok = all(k in report["checks"] for k in ("selfgraph_insert", "route_single_query", "versioned_supersede", "raw_cypher_fallback"))
    report["passed"] = ok
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
