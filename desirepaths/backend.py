"""Graph backend: SelfGraph over HydraDB (preferred) or embedded Kuzu (local dev).

Everything an agent does to the graph goes through `GraphBackend`, which counts
each query it issues (`calls`). Writes go through SelfGraph's typed, versioned
API; reads that need a single multi-hop query (route templates) use SelfGraph's
`run_cypher` escape hatch with a small per-backend dialect, because both
HydraDB and Kuzu store SelfGraph relations as one generic edge label with an
`etype` property, an `is_current` flag and a `revision`.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from typing import Any

from selfgraph import KuzuStore, SelfGraph


@dataclass(frozen=True)
class Dialect:
    name: str
    node: str  # node label holding SelfGraph entities
    edge: str  # edge label holding SelfGraph relations


KUZU = Dialect("kuzu", "N", "R")
HYDRADB = Dialect("hydradb", "Entity", "RELATES")


def hydradb_settings() -> tuple[str, str] | None:
    uri = os.environ.get("HYDRADB_URI") or os.environ.get("SELFGRAPH_URI")
    tok = os.environ.get("HYDRADB_TOKEN") or os.environ.get("SELFGRAPH_AUTH")
    if uri and uri.startswith(("bolt", "neo4j")):
        return uri, tok or ""
    return None


def make_selfgraph(kuzu_path: str, schema: dict | None, fresh: bool, namespace: str = "default") -> tuple[SelfGraph, Dialect]:
    hs = hydradb_settings()
    kw: dict[str, Any] = dict(schema=schema, contradiction="supersede", namespace=namespace)
    if hs:
        from selfgraph import HydraDBStore

        store = HydraDBStore(hs[0], auth=hs[1] or None, database=os.environ.get("HYDRADB_DATABASE"))
        return SelfGraph(store=store, **kw), HYDRADB
    if fresh:
        shutil.rmtree(kuzu_path, ignore_errors=True)
        if os.path.exists(kuzu_path):
            os.remove(kuzu_path)
    return SelfGraph(store=KuzuStore(kuzu_path), **kw), KUZU


def _doc(d: Any) -> dict:
    if isinstance(d, dict):
        return d
    try:
        return json.loads(d) if d else {}
    except (TypeError, ValueError):
        return {}


@dataclass
class Neighbor:
    rel_id: str
    rel_type: str
    revision: int
    direction: str  # "out" or "in", relative to the queried entity
    id: str
    name: str
    type: str


class GraphBackend:
    def __init__(self, sg: SelfGraph, dialect: Dialect, namespace: str = "default"):
        self.sg = sg
        self.d = dialect
        self.ns = namespace
        self.calls = 0  # graph queries issued (HydraDB calls when running on HydraDB)
        self._names: dict[str, tuple[str, str]] = {}  # id -> (name, type), filled at load time

    # ------------------------------------------------------------ loading
    async def load(self, g, chunk: int = 400) -> dict[str, str]:
        """Insert the synthetic graph through SelfGraph's versioned API. Returns logical edge id -> relation id."""
        ents = [dict(id=n.id, type=n.type, name=n.name, properties={"snippet": n.snippet}) for n in g.nodes.values()]
        for n in g.nodes.values():
            self._names[n.id] = (n.name, n.type)
        for i in range(0, len(ents), chunk):
            await self.sg.insert.facts({"entities": ents[i:i + chunk]})
        rel_ids: dict[str, str] = {}
        for i in range(0, len(g.edges), chunk):
            batch = g.edges[i:i + chunk]
            res = await self.sg.insert.facts({"relations": [
                dict(from_entity=e.src, type=e.type, to_entity=e.dst, properties={"lid": e.id}) for e in batch]})
            for e, r in zip(batch, res.relations):
                rel_ids[e.id] = r.id
        return rel_ids

    def name(self, eid: str) -> str:
        return self._names.get(eid, (eid, ""))[0]

    def etype(self, eid: str) -> str:
        return self._names.get(eid, ("", ""))[1]

    # ------------------------------------------------------------ reads
    async def search(self, text: str, k: int = 5) -> list[dict]:
        """Keyword-seeded entity search (SelfGraph BM25 seeds). One graph call."""
        self.calls += 1
        res = await self.sg.retrieve(text, depth=0, k=k, max_nodes=k, budget_tokens=400)
        out = []
        for s in res.seeds[:k]:
            nm, ty = self._names.get(s.id, (s.id, ""))
            out.append({"id": s.id, "name": nm, "type": ty, "score": round(s.score, 3)})
        return out

    async def retrieve_context(self, text: str, depth: int = 2, budget_tokens: int = 1200) -> str:
        """SelfGraph graph retrieval (keyword seeds + bounded BFS). One graph call."""
        self.calls += 1
        res = await self.sg.retrieve(text, depth=depth, k=5, max_nodes=60, budget_tokens=budget_tokens)
        return res.context

    def _start_key(self, eid: str):
        """How a start entity is addressed: Kuzu by its string id, HydraDB by SelfGraph's integer surrogate id."""
        if self.d is HYDRADB:
            from selfgraph.stores.hydradb import _sk

            return _sk(self.ns, eid)
        return eid

    def _ns(self, alias: str) -> str:
        # HydraDB: apply the broad namespace key as a filter, not an index seek (as SelfGraph's HydraDBStore does)
        return f"NOT {alias}.ns <> $ns" if self.d is HYDRADB else f"{alias}.ns = $ns"

    async def neighbors(self, eid: str, rel_type: str | None = None) -> list[Neighbor]:
        """Current relations touching an entity, both directions. One graph call per direction."""
        self.calls += 1
        N, E = self.d.node, self.d.edge
        filt = f"r.is_current = true AND {self._ns('r')}" + (" AND r.etype = $et" if rel_type else "")
        params: dict[str, Any] = {"id": self._start_key(eid), "ns": self.ns}
        if rel_type:
            params["et"] = rel_type
        rows: list[dict] = []
        for dir_, pat, other in (("out", f"(a:{N} {{id: $id}})-[r:{E}]->(b:{N})", "tb"),
                                 ("in", f"(a:{N} {{id: $id}})<-[r:{E}]-(b:{N})", "fa")):
            bid = f"r.{other}" if self.d is HYDRADB else "b.id"
            q = (f"MATCH {pat} WHERE {filt} "
                 f"RETURN r.sid AS sid, r.etype AS et, r.revision AS rev, {bid} AS bid")
            for row in (await self.sg.run_cypher(q, params)).rows:
                rows.append({**row, "dir": dir_})
        out = []
        for row in rows:
            nm, ty = self._names.get(row["bid"], (row["bid"], ""))
            out.append(Neighbor(row["sid"], row["et"], int(row["rev"]), row["dir"], row["bid"], nm, ty))
        out.sort(key=lambda n: (n.rel_type, n.direction, n.name))
        return out

    def compile_route(self, hops: list[tuple[str, str]]) -> str:
        """Compile a typed meta-path to ONE Cypher query over current relations."""
        N, E = self.d.node, self.d.edge
        parts = [f"(n0:{N} {{id: $start}})"]
        where = [] if self.d is HYDRADB else ["n0.ns = $ns"]
        ret = []
        for i, (rel, d) in enumerate(hops, start=1):
            edge = f"-[r{i}:{E} {{etype: $t{i}}}]->" if d == "out" else f"<-[r{i}:{E} {{etype: $t{i}}}]-"
            parts.append(f"{edge}(n{i}:{N})")
            where += [f"r{i}.is_current = true", self._ns(f"r{i}")]
            ret += [f"r{i}.sid AS s{i}", f"r{i}.revision AS v{i}"]
        k = len(hops)
        if self.d is HYDRADB:  # string ids live on the edges (fa/tb); node ids are integer surrogates
            ans = f"r{k}.tb" if hops[-1][1] == "out" else f"r{k}.fa"
        else:
            ans = f"n{k}.id"
        return f"MATCH {''.join(parts)} WHERE {' AND '.join(where)} RETURN {ans} AS answer, {', '.join(ret)}"

    async def run_route(self, hops: list[tuple[str, str]], start: str) -> list[dict]:
        """Execute a learned route template as a single graph query. Returns answers with provenance."""
        self.calls += 1
        params: dict[str, Any] = {"start": self._start_key(start), "ns": self.ns}
        for i, (rel, _) in enumerate(hops, start=1):
            params[f"t{i}"] = rel
        rows = (await self.sg.run_cypher(self.compile_route(hops), params)).rows
        out = []
        for row in rows:
            prov = [(row[f"s{i}"], int(row[f"v{i}"])) for i in range(1, len(hops) + 1)]
            out.append({"answer": row["answer"], "provenance": prov})
        return out

    # ------------------------------------------------------------ writes
    async def supersede(self, src: str, rel_type: str, new_dst: str) -> tuple[str, str]:
        """Replace a single-valued fact (schema max_count=1): SelfGraph retires the old version.

        Returns (retired relation id, new relation id)."""
        self.calls += 1
        old = await self.sg.relations.list(from_entity=src, type=rel_type)
        old_ids = [r.id for r in old.items]
        res = await self.sg.insert.facts({"relations": [dict(from_entity=src, type=rel_type, to_entity=new_dst)]})
        return (old_ids[0] if old_ids else ""), res.relations[0].id

    async def relation_state(self, rel_id: str) -> tuple[bool, int]:
        """(is_current, newest revision) of a relation id."""
        self.calls += 1
        r = await self.sg.relations.get(rel_id)
        if r is None:
            return False, -1
        return bool(r.is_current), int(r.revision)


def selfgraph_schema() -> dict:
    from bench.gen import RELATIONS

    types = sorted({t for _, a, b, _ in RELATIONS for t in (a, b)})
    rels = []
    for t, a, b, mx in RELATIONS:
        frm: dict[str, Any] = {"types": [a]}
        if mx:
            frm["max_count"] = mx
        rels.append({"type": t, "from": frm, "to": {"types": [b]}})
    return {"entities": [{"name": t} for t in types], "relations": rels}
