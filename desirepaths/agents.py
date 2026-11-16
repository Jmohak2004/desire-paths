"""Three agents, one LLM, same questions.

A  VectorRAG     embed node/edge snippets, retrieve iteratively (up to N rounds)
B  GraphAgent    SelfGraph keyword seeds + LLM-driven multi-hop walking, no learning
C  DesirePaths   B plus learned route templates: route a new question to a template, execute it as one graph query
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import numpy as np

from .llm import LLM, Embedder, Meter, parse_json
from .routes import Edge, RouteLibrary, Trace, describe, mask, mentions, verified_paths


@dataclass
class Result:
    answer: list[str]
    meter: Meter
    graph_calls: int = 0
    graph_time_s: float = 0.0
    steps: list[dict] = field(default_factory=list)
    route: str | None = None  # template id used, if any
    fallback: bool = False
    trace: Trace | None = None
    error: str | None = None

    def metrics(self) -> dict:
        m = self.meter.snapshot()
        m.update(graph_calls=self.graph_calls, latency_s=round(self.meter.latency_s + self.graph_time_s, 3),
                 route=self.route, fallback=self.fallback, error=self.error)
        return m


class QB:
    """Per-question view of the shared backend: counts this question's graph calls and graph time."""

    def __init__(self, b):
        self.b = b
        self.calls = 0
        self.time = 0.0

    def __getattr__(self, name):
        attr = getattr(self.b, name)
        if name in ("search", "retrieve_context", "neighbors", "run_route", "relation_state", "supersede"):
            async def wrapped(*a, **k):
                t0 = time.perf_counter()
                try:
                    return await attr(*a, **k)
                finally:
                    self.calls += 1
                    self.time += time.perf_counter() - t0
            return wrapped
        return attr


# --------------------------------------------------------------------------- normalisation and grading
_PREFIX = re.compile(r"^(the|project|service|team|incident|doc|document|pr)\s+", re.I)
_SUFFIX = re.compile(r"\s+(team|project|service)$", re.I)


def norm(name: str) -> str:
    s = name.strip().strip(".'\"").strip()
    for _ in range(2):
        s = _PREFIX.sub("", s)
        s = _SUFFIX.sub("", s)
    return re.sub(r"\s+", " ", s).lower()


def correct(pred: list[str], gold_names: list[str]) -> bool:
    return bool(pred) and {norm(p) for p in pred} == {norm(g) for g in gold_names}


def _same_entity(name: str, mention: str, question: str) -> bool:
    """The resolved entity is the one named in the question: its name matches the mention and occurs in the question."""
    n, m = norm(name), norm(mention)
    return bool(n) and (n == m or (len(m) >= 3 and (m in n or n in m))) and mentions(question, name)


def _names(v) -> list[str]:
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return []


ANSWER_RULE = ('Answer with the exact entity name(s) only, e.g. {"answer": ["Maya Reyes"]}. '
               "Reply with exactly one JSON object and nothing else.")


# --------------------------------------------------------------------------- A: vector RAG
class VectorRAG:
    name = "A_vector"

    def __init__(self, llm: LLM, emb: Embedder, rounds: int = 3, k: int = 8):
        self.llm, self.emb, self.rounds, self.k = llm, emb, rounds, k
        self.texts: list[str] = []
        self.mat: np.ndarray | None = None

    async def index(self, g, name: str) -> None:
        self.texts = [n.snippet for n in g.nodes.values()] + [e.snippet for e in g.edges]
        self.mat = await self.emb.passages(name, self.texts)

    async def answer(self, question: str, backend=None) -> Result:
        meter = Meter()
        res = Result([], meter)
        seen: list[int] = []
        query = question
        for r in range(self.rounds):
            qv = await self.emb.query(query)
            sims = self.mat @ qv
            for i in np.argsort(-sims)[: self.k * 2]:
                if int(i) not in seen and len([x for x in seen]) < self.k * (r + 1):
                    seen.append(int(i))
            ctx = "\n".join(f"- {self.texts[i]}" for i in seen)
            last = r == self.rounds - 1
            instr = (ANSWER_RULE if last else
                     'If the facts are enough, reply {"answer": [names]}. Otherwise reply {"search": "<a new search '
                     'query for the missing fact>"} to retrieve more facts. ' + "Reply with exactly one JSON object.")
            msg = [{"role": "system", "content": "You answer questions about a company using only the retrieved facts."},
                   {"role": "user", "content": f"Question: {question}\n\nRetrieved facts:\n{ctx}\n\n{instr}"}]
            out = parse_json(await self.llm.chat(msg, meter, tag=f"A.r{r}"))
            res.steps.append({"round": r, "query": query, "reply": out})
            if "answer" in out and _names(out["answer"]):
                res.answer = _names(out["answer"])
                return res
            query = str(out.get("search") or question)
        return res


# --------------------------------------------------------------------------- B: graph agent
def schema_text() -> str:
    from .schema import get_relations

    RELATIONS = get_relations()

    return "\n".join(f"  ({a})-[{t}]->({b})" for t, a, b, _ in RELATIONS)


GRAPH_SYSTEM = """You answer multi-hop questions about a company by walking its knowledge graph.
Graph schema (entity types and directed relation types):
{schema}

Each turn, reply with exactly ONE JSON object choosing one action:
  {{"action": "search", "text": "<entity name>"}}          find entities by name; returns ids
  {{"action": "neighbors", "id": "<entity id>"}}            list an entity's current relations (both directions)
  {{"action": "answer", "answer": ["<exact entity name>"]}} finish
Walk one hop at a time: search for the entity named in the question, then follow the relations the question
describes with "neighbors" until you reach the answer. Use ids exactly as returned. Do not guess."""


def _fmt_neighbors(eid: str, name: str, nbs) -> str:
    lines = [f"{name} ({eid}) relations:"]
    for n in nbs:
        arrow = f"-[{n.rel_type}]-> {n.name} ({n.id}, {n.type})" if n.direction == "out" else \
            f"<-[{n.rel_type}]- {n.name} ({n.id}, {n.type})"
        lines.append("  " + arrow)
    return "\n".join(lines) if nbs else f"{name} ({eid}) has no relations."


class GraphAgent:
    name = "B_graph"

    def __init__(self, llm: LLM, max_steps: int = 8):
        self.llm, self.max_steps = llm, max_steps
        self.system = GRAPH_SYSTEM.format(schema=schema_text())

    async def walk(self, question: str, qb: QB, meter: Meter, res: Result) -> tuple[list[str], list[Edge], list[str]]:
        msgs = [{"role": "system", "content": self.system}, {"role": "user", "content": f"Question: {question}"}]
        explored: list[Edge] = []
        roots: list[str] = []
        for step in range(self.max_steps):
            reply = await self.llm.chat(msgs, meter, tag=f"B.s{step}")
            act = parse_json(reply)
            msgs.append({"role": "assistant", "content": json.dumps(act) if act else reply[:500]})
            a = act.get("action")
            if a == "answer" or ("answer" in act and a is None):
                names = _names(act.get("answer"))
                res.steps.append({"step": step, "action": "answer", "answer": names})
                return names, explored, roots
            if a == "search":
                hits = await qb.search(str(act.get("text", ""))[:200])
                for h in hits:
                    if h["id"] not in roots:
                        roots.append(h["id"])
                obs = "Search results:\n" + "\n".join(f"  {h['name']} ({h['id']}, {h['type']})" for h in hits)
            elif a == "neighbors":
                eid = str(act.get("id", ""))
                nbs = await qb.neighbors(eid)
                for n in nbs:
                    src, dst = (eid, n.id) if n.direction == "out" else (n.id, eid)
                    explored.append(Edge(n.rel_id, n.rel_type, n.revision, src, dst))
                obs = _fmt_neighbors(eid, qb.b.name(eid), nbs)
            else:
                obs = 'Invalid action. Reply with one JSON object: search, neighbors, or answer.'
            res.steps.append({"step": step, "action": a, "obs_chars": len(obs)})
            final = step == self.max_steps - 2
            msgs.append({"role": "user", "content": obs + ("\n\nYou must answer now. " + ANSWER_RULE if final else "")})
        return [], explored, roots

    async def answer(self, question: str, backend) -> Result:
        meter = Meter()
        res = Result([], meter)
        qb = QB(backend)
        try:
            res.answer, explored, roots = await self.walk(question, qb, meter, res)
        except Exception as e:  # keep failures in the results instead of crashing the run
            res.error = f"{type(e).__name__}: {e}"[:300]
        res.graph_calls, res.graph_time_s = qb.calls, qb.time
        return res


# --------------------------------------------------------------------------- C: Desire Paths
ROUTER = """You route questions to learned graph routes. Each route answers one kind of question, for any entity
of its start type. Routes:
{routes}

Question: {question}

A route fits only if its path follows exactly the relations the question asks about, in the same order, starting
from the entity the question names and ending at the type of thing the question asks for. If one route fits, reply
{{"route": "<route id>", "entity": "<the exact name of that start entity as written in the question>"}}.
If none fits exactly, reply {{"route": "none"}}. Reply with exactly one JSON object."""


def path_types(start_type: str, hops) -> list[str]:
    """Entity types along a meta-path, from the schema (for a readable, unambiguous route menu)."""
    from .schema import get_relations

    RELATIONS = get_relations()

    ends = {t: (a, b) for t, a, b, _ in RELATIONS}
    out = []
    for rel, d in hops:
        a, b = ends.get(rel, ("", ""))
        out.append(b if d == "out" else a)
    return out


class DesirePaths:
    name = "C_desire"

    def __init__(self, llm: LLM, lib: RouteLibrary, graph_agent: GraphAgent):
        self.llm, self.lib, self.b = llm, lib, graph_agent
        self.learning = True

    def route_menu(self) -> str:
        out = []
        for rt in self.lib.active():
            ex = "; ".join(f'"{e}"' for e in rt.exemplars[:3])
            path = describe(rt.start_type, rt.hops, path_types(rt.start_type, rt.hops))
            out.append(f"- {rt.id}: answers a {path_types(rt.start_type, rt.hops)[-1]} for a given {rt.start_type}; "
                       f"path {path}; examples: {ex}")
        return "\n".join(out)

    async def try_route(self, question: str, qb: QB, meter: Meter, res: Result):
        """Returns (answer names, template, how) or None. how = "shape" (no LLM) or "router" (1 LLM call)."""
        if not self.lib.active():
            return None
        # 1. shape index: a question shape seen in training maps straight to its learned route, for any entity
        hits = await qb.search(question[:300])
        for h in hits:
            if mentions(question, h["name"]):
                rt = self.lib.route_for_shape(mask(question, h["name"], h["type"]))
                if rt is not None and rt.start_type == h["type"]:
                    rows = await qb.run_route(rt.hops, h["id"])
                    if rows:
                        res.steps.append({"route": rt.id, "via": "shape", "start": h["id"], "provenance": rows[0]["provenance"]})
                        return sorted({qb.b.name(r["answer"]) for r in rows}), rt, "shape"
        # 2. unseen phrasing: one LLM call picks a route and names the start entity
        out = parse_json(await self.llm.chat(
            [{"role": "user", "content": ROUTER.format(routes=self.route_menu(), question=question)}],
            meter, tag="C.router"))
        rt = self.lib.get(str(out.get("route", "")))
        res.steps.append({"router": out})
        if rt is None or rt.status != "active":
            return None
        mention = str(out.get("entity", ""))[:200]
        hits = await qb.search(mention) if mention else []
        # entity resolution must agree with the route: right type AND the entity the question names
        start = next((h for h in hits if h["type"] == rt.start_type and _same_entity(h["name"], mention, question)), None)
        if start is None:
            res.steps.append({"route_rejected": rt.id, "reason": "start entity not resolved", "mention": mention})
            return None
        rows = await qb.run_route(rt.hops, start["id"])
        if not rows:
            return None
        res.steps.append({"route": rt.id, "via": "router", "start": start["id"], "provenance": rows[0]["provenance"]})
        return sorted({qb.b.name(r["answer"]) for r in rows}), rt, "router"

    async def answer(self, question: str, backend, gold_names: list[str] | None = None) -> Result:
        meter = Meter()
        res = Result([], meter)
        qb = QB(backend)
        try:
            routed = await self.try_route(question, qb, meter, res)
            if routed is not None:
                names, rt, how = routed
                res.answer, res.route = names, rt.id
                ok = correct(names, gold_names) if gold_names is not None else None
                if self.learning and ok is not None:
                    if how == "shape":
                        self.lib.record_use(rt, ok)  # a shape-index miss is a real route failure
                    elif ok:
                        self.lib.record_use(rt, True)
                    else:
                        self.lib.record_misroute(rt, question)  # router error: learn the right route by walking
                        routed = None
            if routed is None:
                res.fallback = True
                res.route = None
                names, explored, roots = await self.b.walk(question, qb, meter, res)
                res.answer = names
                if self.learning and gold_names is not None:
                    ok = correct(names, gold_names)
                    res.trace = await self.make_trace(question, names, explored, roots, ok, qb)
                    self.lib.observe(res.trace)
        except Exception as e:
            res.error = f"{type(e).__name__}: {e}"[:300]
        res.graph_calls, res.graph_time_s = qb.calls, qb.time
        return res

    async def make_trace(self, question, names, explored, roots, ok, qb: QB) -> Trace:
        """Turn a graph walk into a trace: map answer names to entity ids among explored nodes, verify meta-paths."""
        ids = {}
        for e in explored:
            for n in (e.src, e.dst):
                ids.setdefault(norm(qb.b.name(n)), n)
        ans_ids = [ids[norm(n)] for n in names if norm(n) in ids]
        start = roots[0] if roots else ""
        t = Trace(question, start, qb.b.etype(start), qb.b.name(start), ans_ids, ok)
        if ok and ans_ids and roots:
            # roots ranked by search order; the question's entity is usually the first exact-name hit
            ranked = [r for r in roots if mentions(question, qb.b.name(r))] or roots
            vp = await verified_paths(qb, explored, ranked[:3], ans_ids)
            if vp:
                t.start, t.candidates = vp
                t.start_type, t.start_name = qb.b.etype(t.start), qb.b.name(t.start)
        return t
