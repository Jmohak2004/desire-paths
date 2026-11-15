"""Seeded synthetic enterprise graph and multi-hop questions. No LLM needed.

Everything here is a pure function of the seed, so `make eval` regenerates the
same graph, the same questions and the same gold answers on every machine.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

FIRST = """Ana Ben Chloe Dev Elena Farid Grace Hiro Ines Jonas Kavya Liam Maya Noor Omar Priya Quinn Ravi
Sara Tomas Uma Victor Wen Xavi Yara Zane Aditi Bruno Carmen Dmitri Esha Felix Gita Hugo Ivy Jamal Keiko Lars
Mira Nikhil Olga Pablo Rhea Sven Tara Umar Vera Wade Ximena Yusuf Zoe Arjun Bea Cyrus Dina Emil Freya""".split()
LAST = """Ruiz Okafor Tanaka Mehta Novak Silva Larsen Haddad Kowalski Nguyen Iyer Moreau Fischer Costa Ahmed
Brennan Sato Kapoor Lindqvist Romero Petrov Osei Varga Duarte Ito Mensah Falk Rossi Kaur Holm Abara Bauer
Chandra Dalton Eriksen Farouk Gallo Hayes Ilic Jansen Kimura Lopez Marsh Nair Ortega Park Quiroga Reyes""".split()
ROLES = ["backend engineer", "SRE", "frontend engineer", "data engineer", "engineering manager",
         "security engineer", "product engineer", "ML engineer", "platform engineer", "QA engineer"]
CITIES = ["Bengaluru", "Berlin", "Austin", "Lisbon", "Toronto", "Singapore", "Nairobi", "Seoul", "Dublin"]
TEAM_ADJ = ["Core", "Edge", "Data", "Growth", "Trust", "Cloud", "Mobile", "Search", "Billing", "Identity",
            "Infra", "Payments", "Ledger", "Streaming", "Insights"]
TEAM_NOUN = ["Platform", "Services", "Experience", "Foundations", "Reliability", "Systems"]
CODENAMES = """Falcon Heron Osprey Kestrel Condor Ibis Puffin Raven Swift Tern Wren Lark Finch Egret Merlin
Harrier Petrel Plover Robin Shrike Starling Thrush Vireo Warbler Avocet Bittern Curlew Dunlin Eider Gannet
Hoopoe Jacana Kiwi Loon Macaw Nightjar Oriole Pipit Quail Rail Siskin Toucan Umbra Veery Whimbrel Xenops
Yellowlegs Zosterops Aurora Borealis Cascade Delta Ember Fjord Glacier Harbor Isthmus Juniper Kelp Lagoon
Mesa Nimbus Oasis Prairie Quartz Ridge Sierra Tundra Upland Vale Willow Yucca Zephyr Atlas Beacon Comet
Dynamo Eclipse Fathom Geyser Helix Ion Jetty Krypton Lumen Magnet Nova Orbit Pulsar Quasar Rocket""".split()
SVC_A = ["ledger", "billing", "auth", "search", "catalog", "checkout", "notify", "profile", "inventory",
         "pricing", "fraud", "media", "routing", "session", "metrics", "export", "import", "gateway",
         "scheduler", "payout", "invoice", "audit", "consent", "geo"]
SVC_B = ["api", "worker", "store", "proxy", "indexer", "cache", "sync", "stream"]
DOC_A = ["Quiet", "Amber", "Silent", "Golden", "Hidden", "Northern", "Crimson", "Paper", "Glass", "Iron",
         "Velvet", "Hollow", "Bright", "Lucky", "Second", "Far", "Little", "Open", "Swift", "Winter"]
DOC_B = ["Harbor", "Lantern", "Bridge", "Garden", "Compass", "Meadow", "Signal", "River", "Orchard",
         "Tower", "Canyon", "Mirror", "Anchor", "Field", "Engine", "Island", "Path", "Window"]
SEVERITY = ["SEV1", "SEV2", "SEV3"]
SYMPTOM = ["elevated latency", "error spike", "partial outage", "data lag", "failed deploys", "memory leak",
           "timeouts", "stale cache"]

# Relation types: (type, from_type, to_type, max out-degree per source or None)
RELATIONS = [
    ("MEMBER_OF", "Person", "Team", 1),
    ("WORKS_ON", "Person", "Project", 1),
    ("OWNED_BY", "Project", "Team", 1),
    ("MANAGED_BY", "Team", "Person", 1),
    ("ON_CALL", "Team", "Person", 1),
    ("PART_OF", "Service", "Project", 1),
    ("DEPENDS_ON", "Service", "Service", None),
    ("AFFECTED", "Incident", "Service", 1),
    ("FIXES", "PR", "Incident", 1),
    ("AUTHORED_BY", "PR", "Person", 1),
    ("REVIEWED_BY", "PR", "Person", 1),
    ("DOCUMENTS", "Doc", "Service", 1),
    ("WRITTEN_BY", "Doc", "Person", 1),
]

EDGE_TEXT = {
    "MEMBER_OF": "{a} is a member of the {b} team.",
    "WORKS_ON": "{a} works on project {b}.",
    "OWNED_BY": "Project {a} is owned by the {b} team.",
    "MANAGED_BY": "The {a} team is managed by {b}.",
    "ON_CALL": "{b} is currently on call for the {a} team.",
    "PART_OF": "Service {a} is part of project {b}.",
    "DEPENDS_ON": "Service {a} depends on service {b}.",
    "AFFECTED": "Incident {a} affected service {b}.",
    "FIXES": "{a} fixed incident {b}.",
    "AUTHORED_BY": "{a} was authored by {b}.",
    "REVIEWED_BY": "{a} was reviewed by {b}.",
    "DOCUMENTS": "The document '{a}' documents service {b}.",
    "WRITTEN_BY": "The document '{a}' was written by {b}.",
}


@dataclass
class Node:
    id: str
    type: str
    name: str
    snippet: str


@dataclass
class Edge:
    id: str  # stable logical id, e.g. "e:ON_CALL:team:3"
    type: str
    src: str
    dst: str
    snippet: str


@dataclass
class Graph:
    seed: int
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def out(self, nid: str, etype: str) -> list[str]:
        return [e.dst for e in self.edges if e.src == nid and e.type == etype]

    def inn(self, nid: str, etype: str) -> list[str]:
        return [e.src for e in self.edges if e.dst == nid and e.type == etype]

    def index(self) -> None:
        self._out: dict[tuple[str, str], list[str]] = {}
        self._in: dict[tuple[str, str], list[str]] = {}
        for e in self.edges:
            self._out.setdefault((e.src, e.type), []).append(e.dst)
            self._in.setdefault((e.dst, e.type), []).append(e.src)
        self.out = lambda n, t: self._out.get((n, t), [])  # type: ignore[method-assign]
        self.inn = lambda n, t: self._in.get((n, t), [])  # type: ignore[method-assign]


def _unique(rng: random.Random, make, n: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    while len(out) < n:
        v = make()
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


SIZES = dict(Team=30, Person=480, Project=90, Service=180, Incident=700, PR=800, Doc=300)


def generate(seed: int, sizes: dict[str, int] | None = None) -> Graph:
    rng = random.Random(seed)
    sz = {**SIZES, **(sizes or {})}
    g = Graph(seed=seed)

    def add(t: str, key: str, name: str, snippet: str) -> str:
        nid = f"{t.lower()}:{key}"
        g.nodes[nid] = Node(nid, t, name, snippet)
        return nid

    team_names = _unique(rng, lambda: f"{rng.choice(TEAM_ADJ)} {rng.choice(TEAM_NOUN)}", sz["Team"])
    teams = [add("Team", str(i), n, f"{n} is an engineering team.") for i, n in enumerate(team_names)]
    pnames = _unique(rng, lambda: f"{rng.choice(FIRST)} {rng.choice(LAST)}", sz["Person"])
    people = [add("Person", str(i), n, f"{n} is a {rng.choice(ROLES)} based in {rng.choice(CITIES)}.")
              for i, n in enumerate(pnames)]
    projn = rng.sample(CODENAMES, k=min(sz["Project"], len(CODENAMES)))
    while len(projn) < sz["Project"]:
        projn.append(f"{rng.choice(CODENAMES)} {len(projn)}")
    projects = [add("Project", str(i), n, f"Project {n} is an internal engineering initiative.")
                for i, n in enumerate(projn)]
    sn = _unique(rng, lambda: f"{rng.choice(SVC_A)}-{rng.choice(SVC_B)}", min(sz["Service"], len(SVC_A) * len(SVC_B)))
    services = [add("Service", str(i), n, f"{n} is a production service.") for i, n in enumerate(sn)]
    inc_ids = _unique(rng, lambda: f"INC-{rng.randint(1000, 9999)}", sz["Incident"])
    incidents = [add("Incident", str(i), n, f"{n} was a {rng.choice(SEVERITY)} incident with {rng.choice(SYMPTOM)}.")
                 for i, n in enumerate(inc_ids)]
    pr_ids = _unique(rng, lambda: f"PR-{rng.randint(10000, 99999)}", sz["PR"])
    prs = [add("PR", str(i), n, f"{n} is a pull request.") for i, n in enumerate(pr_ids)]
    dn = _unique(rng, lambda: f"{rng.choice(DOC_A)} {rng.choice(DOC_B)} Notes", min(sz["Doc"], len(DOC_A) * len(DOC_B)))
    docs = [add("Doc", str(i), n, f"'{n}' is an internal design document.") for i, n in enumerate(dn)]

    counter: dict[str, int] = {}

    def link(t: str, a: str, b: str) -> None:
        k = counter.get(t, 0)
        counter[t] = k + 1
        text = EDGE_TEXT[t].format(a=g.nodes[a].name, b=g.nodes[b].name)
        g.edges.append(Edge(f"e:{t}:{k}", t, a, b, text))

    # Every team gets members; managers and on-call are drawn from members.
    members: dict[str, list[str]] = {t: [] for t in teams}
    for i, p in enumerate(people):
        t = teams[i % len(teams)] if i < len(teams) * 2 else rng.choice(teams)
        members[t].append(p)
        link("MEMBER_OF", p, t)
    for t in teams:
        mgr, oncall = rng.sample(members[t], 2)
        link("MANAGED_BY", t, mgr)
        link("ON_CALL", t, oncall)
    for i, pr in enumerate(projects):
        link("OWNED_BY", pr, teams[i % len(teams)] if i < len(teams) else rng.choice(teams))
    for p in people:  # cross-team work: project is not necessarily owned by the person's team
        link("WORKS_ON", p, rng.choice(projects))
    for i, s in enumerate(services):
        link("PART_OF", s, projects[i % len(projects)] if i < len(projects) else rng.choice(projects))
    for s in services:
        for d in rng.sample(services, k=rng.randint(0, 2)):
            if d != s:
                link("DEPENDS_ON", s, d)
    for inc in incidents:
        link("AFFECTED", inc, rng.choice(services))
    fixers = rng.sample(prs, k=len(incidents))
    for inc, pr in zip(incidents, fixers):
        link("FIXES", pr, inc)
    for pr in prs:
        a, r = rng.sample(people, 2)
        link("AUTHORED_BY", pr, a)
        link("REVIEWED_BY", pr, r)
    for d in docs:
        link("DOCUMENTS", d, rng.choice(services))
        link("WRITTEN_BY", d, rng.choice(people))
    g.index()
    return g


# ---------------------------------------------------------------- questions
# Each template: start type, hop spec [(rel, direction)], and paraphrases.
# Direction "out" follows src->dst, "in" follows dst->src.
QTEMPLATES = {
    "oncall_for_person_project": dict(
        start="Person", hops=[("WORKS_ON", "out"), ("OWNED_BY", "out"), ("ON_CALL", "out")],
        phrasings=[
            "Who is currently on call for the team that owns the project {x} works on?",
            "{x} works on some project. Which person is on call for the team owning that project?",
            "I need to page someone about {x}'s project. Who is on call for the owning team?",
        ]),
    "manager_of_project_team": dict(
        start="Project", hops=[("OWNED_BY", "out"), ("MANAGED_BY", "out")],
        phrasings=[
            "Who manages the team that owns project {x}?",
            "Project {x} belongs to a team. Who is that team's manager?",
            "Which manager is responsible for the team behind project {x}?",
        ]),
    "team_owning_incident_service": dict(
        start="Incident", hops=[("AFFECTED", "out"), ("PART_OF", "out"), ("OWNED_BY", "out")],
        phrasings=[
            "Which team owns the project containing the service affected by incident {x}?",
            "Incident {x} hit a service. Which team owns the project that service is part of?",
            "Route incident {x} to the right team: which team owns the affected service's project?",
        ]),
    "manager_of_fixer_team": dict(
        start="Incident", hops=[("FIXES", "in"), ("AUTHORED_BY", "out"), ("MEMBER_OF", "out"), ("MANAGED_BY", "out")],
        phrasings=[
            "Who manages the team of the person who authored the PR that fixed incident {x}?",
            "A PR fixed incident {x}. Who is the manager of the team its author belongs to?",
            "Find the author of the fix for incident {x}; who manages that author's team?",
        ]),
    "project_of_doc_service": dict(
        start="Doc", hops=[("DOCUMENTS", "out"), ("PART_OF", "out")],
        phrasings=[
            "Which project is the service documented in '{x}' part of?",
            "The document '{x}' describes a service. Which project does that service belong to?",
            "'{x}' documents a service; name the project that service is part of.",
        ]),
    "oncall_for_service": dict(
        start="Service", hops=[("PART_OF", "out"), ("OWNED_BY", "out"), ("ON_CALL", "out")],
        phrasings=[
            "Who is on call for the team that owns the project service {x} is part of?",
            "Service {x} is down. Who is on call for the team owning its project?",
            "Which person should be paged for service {x}, i.e. who is on call for the team owning its project?",
        ]),
}


@dataclass
class Question:
    qid: str
    template: str  # the gold template id; agents never see it
    text: str
    start: str  # start entity id; agents never see it
    gold: list[str]  # gold answer entity ids
    gold_names: list[str]
    path: list[str]  # gold entity path (for heal-test selection)


def walk(g: Graph, start: str, hops) -> tuple[list[str], list[list[str]]]:
    frontier = [start]
    layers = [[start]]
    for rel, d in hops:
        nxt: list[str] = []
        for n in frontier:
            nxt.extend(g.out(n, rel) if d == "out" else g.inn(n, rel))
        frontier = sorted(set(nxt))
        layers.append(frontier)
    return frontier, layers


def make_questions(g: Graph, per_template_train: int, per_template_test: int, seed: int):
    """Train and held-out questions with disjoint start entities (and disjoint phrasing pools)."""
    rng = random.Random(seed * 7919 + 1)
    train: list[Question] = []
    test: list[Question] = []
    by_type: dict[str, list[str]] = {}
    for n in g.nodes.values():
        by_type.setdefault(n.type, []).append(n.id)
    used: set[str] = set()
    for tid, spec in QTEMPLATES.items():
        cands = list(by_type[spec["start"]])
        rng.shuffle(cands)
        good = []
        for c in cands:
            if c in used:
                continue
            ans, layers = walk(g, c, spec["hops"])
            if len(ans) == 1:  # unambiguous single answer
                good.append((c, ans, [x[0] for x in layers if x]))
            if len(good) >= per_template_train + per_template_test:
                break
        for i, (c, ans, path) in enumerate(good):
            used.add(c)
            is_train = i < per_template_train
            # train sees phrasings 0-1; held-out draws from all three (phrasing 2 is never seen in train)
            ph = spec["phrasings"][i % 2] if is_train else spec["phrasings"][i % 3]
            q = Question(
                qid=f"{'tr' if is_train else 'te'}-{tid}-{i}", template=tid,
                text=ph.format(x=g.nodes[c].name), start=c, gold=ans,
                gold_names=[g.nodes[a].name for a in ans], path=path)
            (train if is_train else test).append(q)
    rng.shuffle(train)
    return train, test


if __name__ == "__main__":
    g = generate(0)
    tr, te = make_questions(g, 8, 4, 0)
    print(len(g.nodes), "nodes", len(g.edges), "edges", len(tr), "train", len(te), "test")
    for q in te[:6]:
        print(q.template, "|", q.text, "->", q.gold_names)
