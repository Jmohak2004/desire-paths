"""Desire Paths: learn typed route templates from successful agent traversals.

A *trace* is one answered question: the start entity, the typed meta-path the
agent actually walked from it to the answer (relation types plus direction, not
entities), the relation ids and revisions it crossed, and whether it succeeded.

A *route template* groups traces by (start type, meta-path). Once it has enough
successful support it is promoted and can answer a NEW question about an
entity it has never seen in one graph query, because it is bound to types, not
instances. That is what makes it a route and not a cache.

Each template keeps provenance: the relation ids and revisions behind its
supporting traces. When one of those relations changes (SelfGraph retires the
old version), the template retires. Revalidation re-binds its supporting
traces against the current graph; if the meta-path still holds for enough of
them it comes back as a new version, otherwise it stays retired until fresh
traversals re-earn it.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import asdict, dataclass, field

Hop = tuple[str, str]  # (relation type, "out" | "in")


@dataclass
class Candidate:
    hops: list[Hop]
    provenance: list[tuple[str, int]]  # (relation id, revision) crossed, in order


@dataclass
class Trace:
    question: str
    start: str
    start_type: str
    start_name: str
    answer: list[str]
    success: bool
    candidates: list[Candidate] = field(default_factory=list)  # verified meta-paths that explain the answer


@dataclass
class Edge:
    rel_id: str
    rel_type: str
    revision: int
    src: str
    dst: str


def extract_path(explored: list[Edge], roots: list[str], answers: list[str]) -> tuple[str, list[Hop], list[tuple[str, int]]] | None:
    """Shortest path through the edges the agent actually looked at, from a root it searched to an answer.

    Returns (start id, typed hops, provenance) or None when the answer is not reachable through explored edges.
    """
    adj: dict[str, list[tuple[str, Hop, tuple[str, int]]]] = {}
    for e in explored:
        adj.setdefault(e.src, []).append((e.dst, (e.rel_type, "out"), (e.rel_id, e.revision)))
        adj.setdefault(e.dst, []).append((e.src, (e.rel_type, "in"), (e.rel_id, e.revision)))
    targets = set(answers)
    best = None
    for root in roots:
        prev: dict[str, tuple[str, Hop, tuple[str, int]] | None] = {root: None}
        dq = deque([root])
        hit = None
        while dq:
            n = dq.popleft()
            if n in targets and n != root:
                hit = n
                break
            for m, hop, prov in adj.get(n, []):
                if m not in prev:
                    prev[m] = (n, hop, prov)
                    dq.append(m)
        if hit is None:
            continue
        hops: list[Hop] = []
        provs: list[tuple[str, int]] = []
        cur = hit
        while prev[cur] is not None:
            p, hop, prov = prev[cur]  # type: ignore[misc]
            hops.append(hop)
            provs.append(prov)
            cur = p
        hops.reverse()
        provs.reverse()
        if best is None or len(hops) < len(best[1]):
            best = (root, hops, provs)
    return best


def candidate_paths(explored: list[Edge], roots: list[str], answers: list[str], slack: int = 2, limit: int = 24,
                    max_hops: int = 5) -> list[tuple[str, list[Hop]]]:
    """Distinct typed meta-paths (walks up to shortest+slack hops, no edge reused) from a root to an answer.

    Walks may revisit an entity: a PR's author can also be the manager of the author's own team.
    """
    adj: dict[str, list[tuple[str, Hop, str]]] = {}
    for e in explored:
        adj.setdefault(e.src, []).append((e.dst, (e.rel_type, "out"), e.rel_id))
        adj.setdefault(e.dst, []).append((e.src, (e.rel_type, "in"), e.rel_id))
    targets = set(answers)
    out: list[tuple[str, list[Hop]]] = []
    seen: set[tuple] = set()
    for root in roots:
        dist = {root: 0}
        dq = deque([root])
        while dq:
            n = dq.popleft()
            for m, _, _ in adj.get(n, []):
                if m not in dist:
                    dist[m] = dist[n] + 1
                    dq.append(m)
        reach = [dist[t] for t in targets if t in dist and t != root]
        if not reach:
            continue
        maxlen = min(min(reach) + slack, max_hops)

        def dfs(n, hops, used):
            if len(out) >= limit:
                return
            if n in targets and hops:
                key = (root, tuple(hops))
                if key not in seen:
                    seen.add(key)
                    out.append((root, list(hops)))
            if len(hops) >= maxlen:
                return
            for m, hop, rid in adj.get(n, []):
                if rid not in used:
                    dfs(m, hops + [hop], used | {rid})

        dfs(root, [], frozenset())
    out.sort(key=lambda x: len(x[1]))
    return out


async def verified_paths(backend, explored: list[Edge], roots: list[str], answers: list[str], slack: int = 2):
    """Meta-paths through the explored edges whose single-query execution from the root returns exactly the answer.

    Drops paths that merely touch the answer (e.g. 'any member of the team' vs 'the on-call person'). A path that
    is right only by coincidence for this one entity survives here; cross-trace support in RouteLibrary removes it.
    Returns (root, [Candidate]) or None.
    """
    want = sorted(set(answers))
    by_root: dict[str, list[Candidate]] = {}
    for root, hops in candidate_paths(explored, roots, answers, slack=slack):
        rows = await backend.run_route(hops, root)
        if rows and sorted({r["answer"] for r in rows}) == want:
            by_root.setdefault(root, []).append(Candidate(hops, rows[0]["provenance"]))
    if not by_root:
        return None
    root = min(by_root, key=lambda r: roots.index(r) if r in roots else 99)
    return root, by_root[root]


def mask(question: str, name: str, etype: str) -> str:
    """The question's shape: the entity name replaced by its type (whole-word match only)."""
    return re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", "{" + etype + "}", question, flags=re.IGNORECASE)


def mentions(question: str, name: str) -> bool:
    return bool(name) and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", question, flags=re.IGNORECASE) is not None


def route_key(start_type: str, hops: list[Hop]) -> str:
    return start_type + "|" + "|".join(f"{r}:{d}" for r, d in hops)


def route_id(key: str) -> str:
    """Stable id from the meta-path itself, so runs (and the request cache) are reproducible under concurrency."""
    return "R" + hashlib.sha1(key.encode()).hexdigest()[:4]


def describe(start_type: str, hops: list[Hop], types: list[str] | None = None) -> str:
    s = f"({start_type})"
    for i, (r, d) in enumerate(hops):
        nxt = f"({types[i]})" if types and i < len(types) else "()"
        s += f"-[{r}]->{nxt}" if d == "out" else f"<-[{r}]-{nxt}"
    return s


@dataclass
class Support:
    start: str
    provenance: list[tuple[str, int]]


@dataclass
class RouteTemplate:
    id: str
    start_type: str
    hops: list[Hop]
    answer_type: str = ""
    status: str = "candidate"  # candidate | active | retired
    version: int = 0
    successes: int = 0
    failures: int = 0
    support: list[Support] = field(default_factory=list)
    exemplars: list[str] = field(default_factory=list)
    uses: int = 0
    events: list[dict] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        n = self.successes + self.failures
        return self.successes / n if n else 0.0

    def depends_on(self) -> set[str]:
        return {rid for s in self.support for rid, _ in s.provenance}

    def signature(self) -> str:
        return describe(self.start_type, self.hops)


class RouteLibrary:
    def __init__(self, min_support: int = 3, min_success: float = 0.8, max_exemplars: int = 4):
        self.min_support = min_support
        self.min_success = min_success
        self.max_exemplars = max_exemplars
        self.templates: dict[str, RouteTemplate] = {}
        self.shapes: dict[str, dict] = {}  # masked question shape -> {n, fail, hits: {route key: count}}
        self._n = 0
        self.clock = 0  # logical time (round number), stamped on events

    # ---------------------------------------------------------------- learning
    def observe(self, t: Trace) -> list[RouteTemplate]:
        """Log one traversal. Every verified meta-path of a successful trace is a hypothesis for its question shape."""
        shape = mask(t.question, t.start_name, t.start_type)
        st = self.shapes.setdefault(shape, {"n": 0, "fail": 0, "hits": {}})
        if not t.success or not t.candidates:
            st["fail"] += 1
            return []
        st["n"] += 1
        touched = []
        for c in t.candidates:
            key = route_key(t.start_type, c.hops)
            rt = self.templates.get(key)
            if rt is None:
                rt = RouteTemplate(id=route_id(key), start_type=t.start_type, hops=list(c.hops))
                self.templates[key] = rt
            rt.support.append(Support(t.start, list(c.provenance)))
            st["hits"][key] = st["hits"].get(key, 0) + 1
            touched.append(rt)
        return touched

    def _best_by_shape(self) -> dict[str, tuple[str, int]]:
        """For each question shape, the meta-path that explains it best: most support, then fewest hops.

        A path counts only if it explains at least min_success of the shape's successful traces. Ties on support are
        common (a detour through the team's manager and back is always 'correct'); the shorter route wins.
        """
        best: dict[str, tuple[str, int]] = {}
        for shape, st in self.shapes.items():
            ok = [(k, c) for k, c in st["hits"].items() if st["n"] and c / st["n"] >= self.min_success]
            if ok:
                k, c = min(ok, key=lambda kc: (-kc[1], len(self.templates[kc[0]].hops), kc[0]))
                best[shape] = (k, c)
        return best

    def record_use(self, rt: RouteTemplate, correct: bool) -> None:
        rt.uses += 1
        if correct:
            rt.successes += 1
        else:
            rt.failures += 1

    def promote(self) -> list[RouteTemplate]:
        promoted = []
        best = self._best_by_shape()
        for key, rt in self.templates.items():
            att = [(shape, c) for shape, (k, c) in best.items() if k == key]
            support = sum(c for _, c in att)
            rt.exemplars = [s for s, _ in sorted(att, key=lambda x: (-x[1], x[0]))][: self.max_exemplars]
            used_badly = rt.uses >= 3 and rt.success_rate < self.min_success
            if rt.status == "candidate" and support >= self.min_support and not used_badly:
                rt.status = "active"
                rt.version += 1
                rt.events.append({"t": self.clock, "event": "promoted", "version": rt.version, "support": support})
                promoted.append(rt)
            elif rt.status == "active" and (support < self.min_support or used_badly):
                rt.status = "candidate"
                rt.events.append({"t": self.clock, "event": "demoted", "support": support,
                                  "use_success": round(rt.success_rate, 2)})
        return promoted

    def active(self) -> list[RouteTemplate]:
        return sorted((rt for rt in self.templates.values() if rt.status == "active"), key=lambda r: r.id)

    def route_for_shape(self, shape: str) -> RouteTemplate | None:
        """The active route learned for an exact question shape, if any (no LLM needed)."""
        hit = self._best_by_shape().get(shape)
        if hit is None:
            return None
        rt = self.templates.get(hit[0])
        return rt if rt is not None and rt.status == "active" else None

    def record_misroute(self, rt: RouteTemplate, question: str) -> None:
        """The router picked this route for a question it does not answer. A router error, not a route error."""
        rt.events.append({"t": self.clock, "event": "misrouted_to", "question": question[:120]})

    def get(self, rid: str) -> RouteTemplate | None:
        return next((rt for rt in self.templates.values() if rt.id == rid), None)

    # ---------------------------------------------------------------- retirement
    def on_relation_change(self, rel_id: str, reason: str = "fact changed") -> list[RouteTemplate]:
        """A relation this library may depend on was retired or re-versioned: retire dependent templates."""
        hit = []
        for rt in self.templates.values():
            if rt.status == "active" and rel_id in rt.depends_on():
                rt.status = "retired"
                rt.events.append({"t": self.clock, "event": "retired", "version": rt.version, "relation": rel_id, "reason": reason})
                hit.append(rt)
        return hit

    async def revalidate(self, backend) -> list[RouteTemplate]:
        """Re-bind retired templates' support against the current graph and re-promote those that still hold."""
        rebuilt = []
        for rt in self.templates.values():
            if rt.status != "retired":
                continue
            fresh: list[Support] = []
            for s in rt.support:
                stale = False
                for rid, rev in s.provenance:
                    cur, newest = await backend.relation_state(rid)
                    if not cur or newest != rev:
                        stale = True
                        break
                if not stale:
                    fresh.append(s)
                    continue
                rows = await backend.run_route(rt.hops, s.start)  # does the meta-path still hold from here?
                if len(rows) == 1:
                    fresh.append(Support(s.start, rows[0]["provenance"]))
            dropped = len(rt.support) - len(fresh)
            rt.support = fresh
            if len(fresh) >= self.min_support:
                rt.status = "active"
                rt.version += 1
                rt.events.append({"t": self.clock, "event": "rebuilt", "version": rt.version, "support": len(fresh), "rebound": dropped})
                rebuilt.append(rt)
            else:
                rt.status = "candidate"
                rt.events.append({"t": self.clock, "event": "awaiting_relearn", "support": len(fresh)})
        return rebuilt

    # ---------------------------------------------------------------- persistence
    def to_json(self) -> dict:
        return {"min_support": self.min_support, "min_success": self.min_success, "shapes": self.shapes,
                "templates": [asdict(rt) | {"signature": rt.signature(), "success_rate": rt.success_rate}
                              for rt in self.templates.values()]}

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=1)

    @classmethod
    def from_json(cls, d: dict) -> "RouteLibrary":
        lib = cls(min_support=d.get("min_support", 3), min_success=d.get("min_success", 0.8))
        lib.shapes = d.get("shapes", {})
        for t in d.get("templates", []):
            rt = RouteTemplate(
                id=t["id"], start_type=t["start_type"], hops=[tuple(h) for h in t["hops"]],
                answer_type=t.get("answer_type", ""), status=t["status"], version=t["version"],
                successes=t.get("successes", 0), failures=t.get("failures", 0),
                support=[Support(s["start"], [tuple(p) for p in s["provenance"]]) for s in t.get("support", [])],
                exemplars=t.get("exemplars", []), uses=t.get("uses", 0), events=t.get("events", []))
            lib.templates[route_key(rt.start_type, rt.hops)] = rt
        return lib

    @classmethod
    def load(cls, path: str) -> "RouteLibrary":
        with open(path) as f:
            return cls.from_json(json.load(f))
