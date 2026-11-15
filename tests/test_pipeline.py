"""End-to-end plumbing of agents B and C with a scripted oracle LLM (no API calls).

The oracle walks the gold path one action per call, exactly like a perfect graph agent would, so this tests the
real JSON action loop, trace extraction, meta-path verification, promotion, routing and single-query execution.
It says nothing about real-model accuracy; that is what `make eval` measures.
"""
import asyncio
import json

import pytest

from bench.gen import QTEMPLATES, generate, make_questions
from desirepaths.agents import DesirePaths, GraphAgent, correct
from desirepaths.backend import GraphBackend, make_selfgraph, selfgraph_schema
from desirepaths.llm import Meter
from desirepaths.routes import RouteLibrary

SMALL = dict(Team=8, Person=60, Project=16, Service=24, Incident=40, PR=50, Doc=20)


class OracleLLM:
    def __init__(self, g, questions):
        self.g = g
        self.by_text = {q.text: q for q in questions}
        self.lib: RouteLibrary | None = None

    async def chat(self, messages, meter: Meter, max_tokens=400, tag=""):
        meter.calls += 1
        meter.input_tokens += sum(len(m["content"]) // 4 for m in messages)
        if tag == "C.router":
            text = messages[0]["content"]
            q = next(q for t, q in self.by_text.items() if f"Question: {t}" in text)
            hops = [tuple(h) for h in QTEMPLATES[q.template]["hops"]]
            rt = next((r for r in self.lib.active() if r.hops == hops), None)
            return json.dumps({"route": rt.id if rt else "none", "entity": self.g.nodes[q.start].name})
        q = self.by_text[messages[1]["content"].removeprefix("Question: ")]
        step = sum(1 for m in messages if m["role"] == "assistant")
        if step == 0:
            return json.dumps({"action": "search", "text": self.g.nodes[q.start].name})
        if step <= len(q.path) - 1:
            return json.dumps({"action": "neighbors", "id": q.path[step - 1]})
        return json.dumps({"action": "answer", "answer": q.gold_names})


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    g = generate(5, SMALL)
    loop = asyncio.new_event_loop()
    sg, d, ns = make_selfgraph(str(tmp_path_factory.mktemp("kz") / "p.kuzu"), selfgraph_schema(), fresh=True, namespace="p")
    loop.run_until_complete(sg.__aenter__())
    b = GraphBackend(sg, d, namespace=ns)
    loop.run_until_complete(b.load(g))
    yield g, b, loop
    loop.run_until_complete(sg.__aexit__(None, None, None))
    loop.close()


def test_c_learns_routes_and_cuts_llm_calls_on_heldout(world):
    g, b, loop = world
    train, test = make_questions(g, 6, 2, 5)
    llm = OracleLLM(g, train + test)
    lib = RouteLibrary(min_support=3)
    llm.lib = lib
    B = GraphAgent(llm)
    C = DesirePaths(llm, lib, B)

    async def run():
        b_res = [await B.answer(q.text, b) for q in test]
        for q in train:
            await C.answer(q.text, b, gold_names=q.gold_names)
        lib.promote()
        C.learning = False
        c_res = [await C.answer(q.text, b) for q in test]
        return b_res, c_res

    b_res, c_res = loop.run_until_complete(run())
    assert all(correct(r.answer, q.gold_names) for r, q in zip(b_res, test))
    assert all(correct(r.answer, q.gold_names) for r, q in zip(c_res, test))
    assert len(lib.active()) == len(QTEMPLATES)
    routed = [r for r in c_res if r.route]
    assert len(routed) == len(test)
    via = [next(s["via"] for s in r.steps if "via" in s) for r in routed]
    # seen phrasings: shape index, 0 LLM calls (search + route query); unseen phrasing: router, 1 LLM call
    assert all((v == "shape" and r.meter.calls == 0 and r.graph_calls == 2) or
               (v == "router" and r.meter.calls == 1 and r.graph_calls == 3) for v, r in zip(via, routed))
    assert "shape" in via
    assert sum(r.meter.calls for r in c_res) < sum(r.meter.calls for r in b_res) / 3
