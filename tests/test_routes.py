"""Route learning, template execution and retirement, against a real SelfGraph graph (Kuzu, or HydraDB if configured)."""
import asyncio

import pytest

from bench.gen import QTEMPLATES, generate, make_questions, walk
from desirepaths.backend import GraphBackend, make_selfgraph, selfgraph_schema
from desirepaths.routes import Candidate, Edge, RouteLibrary, Trace, mask, verified_paths

SMALL = dict(Team=8, Person=60, Project=16, Service=24, Incident=40, PR=50, Doc=20)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    g = generate(3, SMALL)
    path = str(tmp_path_factory.mktemp("kz") / "t.kuzu")
    loop = asyncio.new_event_loop()
    sg, d, ns = make_selfgraph(path, selfgraph_schema(), fresh=True, namespace="test")
    loop.run_until_complete(sg.__aenter__())
    b = GraphBackend(sg, d, namespace=ns)
    loop.run_until_complete(b.load(g))
    yield g, b, loop
    loop.run_until_complete(sg.__aexit__(None, None, None))
    loop.close()


async def oracle_trace(b: GraphBackend, g, q, success=True) -> Trace:
    """Simulate a graph agent: expand neighbors along the gold path, then extract the walked meta-path."""
    explored: list[Edge] = []
    frontier = [q.start]
    for rel, d in QTEMPLATES[q.template]["hops"]:
        nxt = []
        for n in frontier:
            for nb in await b.neighbors(n):
                src, dst = (n, nb.id) if nb.direction == "out" else (nb.id, n)
                explored.append(Edge(nb.rel_id, nb.rel_type, nb.revision, src, dst))
                if nb.rel_type == rel and nb.direction == d:
                    nxt.append(nb.id)
        frontier = nxt
    start, cands = await verified_paths(b, explored, [q.start], q.gold)
    return Trace(q.text, start, g.nodes[start].type, g.nodes[start].name, q.gold, success, cands)


def test_extract_path_recovers_typed_metapath(world):
    """The gold meta-path is always among the verified hypotheses; each carries per-hop provenance."""
    g, b, loop = world
    tr, _ = make_questions(g, 4, 2, 3)
    for q in tr:
        t = loop.run_until_complete(oracle_trace(b, g, q))
        gold = [tuple(h) for h in QTEMPLATES[q.template]["hops"]]
        assert gold in [c.hops for c in t.candidates], q.template
        assert all(len(c.provenance) == len(c.hops) for c in t.candidates)


def test_coincidental_shortcut_is_not_promoted(world):
    """Traces of one question shape: the true path explains all of them, a coincidental shortcut only some."""
    g, b, loop = world
    tr, _ = make_questions(g, 12, 0, 3)
    lib = RouteLibrary(min_support=3)
    for q in tr:
        lib.observe(loop.run_until_complete(oracle_trace(b, g, q)))
    lib.promote()
    golds = {tuple(map(tuple, s["hops"])) for s in QTEMPLATES.values()}
    assert lib.active()
    assert all(tuple(rt.hops) in golds for rt in lib.active()), [rt.signature() for rt in lib.active()]


def test_promotion_needs_support_and_success():
    lib = RouteLibrary(min_support=3, min_success=0.8)
    hops = [("WORKS_ON", "out"), ("OWNED_BY", "out")]
    mk = lambda i, ok: Trace(f"q about P{i}", f"person:{i}", "Person", f"P{i}", ["x"], ok, [Candidate(hops, [(f"r{i}", 1)])])
    for i in range(2):
        lib.observe(mk(i, True))
    assert lib.promote() == []  # support 2 < 3
    lib.observe(mk(2, True))
    rt = lib.promote()
    assert len(rt) == 1 and rt[0].exemplars == ["q about {Person}"]
    for _ in range(3):
        lib.record_use(rt[0], correct=False)  # executions judged wrong -> demoted
    lib.promote()
    assert lib.active() == []


def test_mask_generalises_exemplar():
    assert mask("Who manages the team that owns project Mesa?", "Mesa", "Project") == "Who manages the team that owns project {Project}?"


def test_template_answers_unseen_entities(world):
    """Learned on train entities, executed on held-out entities it never saw: one graph query each, gold answers."""
    g, b, loop = world
    tr, te = make_questions(g, 4, 3, 3)
    lib = RouteLibrary(min_support=3)
    for q in tr:
        lib.observe(loop.run_until_complete(oracle_trace(b, g, q)))
    lib.promote()
    assert lib.active(), "no template promoted"
    seen = {q.start for q in tr}
    checked = 0
    for q in te:
        assert q.start not in seen
        rt = next((r for r in lib.active() if r.hops == [tuple(h) for h in QTEMPLATES[q.template]["hops"]]), None)
        if rt is None:
            continue
        before = b.calls
        rows = loop.run_until_complete(b.run_route(rt.hops, q.start))
        assert b.calls - before == 1
        assert [r["answer"] for r in rows] == q.gold
        checked += 1
    assert checked >= 3


def test_fact_change_retires_and_rebuilds_template(world):
    g, b, loop = world
    tr, _ = make_questions(g, 6, 0, 3)
    lib = RouteLibrary(min_support=3)
    qs = [q for q in tr if q.template == "oncall_for_person_project"]
    for q in qs:
        lib.observe(loop.run_until_complete(oracle_trace(b, g, q)))
    lib.promote()
    rt = lib.active()[0]
    sup = rt.support[0]
    team = walk(g, sup.start, QTEMPLATES["oncall_for_person_project"]["hops"][:2])[0][0]
    old_oncall = g.out(team, "ON_CALL")[0]
    new_oncall = next(p for p in g.inn(team, "MEMBER_OF") if p != old_oncall)

    old_rel, new_rel = loop.run_until_complete(b.supersede(team, "ON_CALL", new_oncall))
    assert old_rel in rt.depends_on()
    retired = lib.on_relation_change(old_rel)
    assert rt in retired and rt.status == "retired"

    rebuilt = loop.run_until_complete(lib.revalidate(b))
    assert rt in rebuilt and rt.status == "active" and rt.version == 2
    assert old_rel not in rt.depends_on() and new_rel in rt.depends_on()
    rows = loop.run_until_complete(b.run_route(rt.hops, sup.start))
    assert [r["answer"] for r in rows] == [new_oncall]  # healed route reads the current fact


def test_library_roundtrips_through_json(tmp_path):
    lib = RouteLibrary(min_support=1)
    hops = [("WORKS_ON", "out"), ("OWNED_BY", "out")]
    lib.observe(Trace("q about P1", "person:1", "Person", "P1", ["x"], True, [Candidate(hops, [("r1", 1)])]))
    lib.promote()
    lib.save(str(tmp_path / "l.json"))
    back = RouteLibrary.load(str(tmp_path / "l.json"))
    rt = back.active()[0]
    assert rt.status == "active" and rt.hops == hops and rt.depends_on() == {"r1"}
    assert back.on_relation_change("r1") == [rt]


def test_mask_is_whole_word_and_ids_are_stable():
    assert mask("Which project is the description of Ion?", "Ion", "Project") == "Which project is the description of {Project}?"
    from desirepaths.routes import route_id, route_key
    k = route_key("Person", [("WORKS_ON", "out")])
    assert route_id(k) == route_id(k) and route_id(k).startswith("R")
