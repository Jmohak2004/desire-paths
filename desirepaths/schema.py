"""The relation schema the agents and routes work over: (type, from entity type, to entity type, max out-degree).

Desire Paths is domain-agnostic. Register your graph's relation types with `set_relations(...)`. When none are
registered, the synthetic enterprise benchmark schema (`bench.gen.RELATIONS`) is used.
"""
from __future__ import annotations

Relation = tuple[str, str, str, "int | None"]
_RELATIONS: list[Relation] | None = None


def set_relations(relations: list[Relation]) -> None:
    global _RELATIONS
    _RELATIONS = [tuple(r) for r in relations]  # type: ignore[misc]


def get_relations() -> list[Relation]:
    if _RELATIONS is None:
        from bench.gen import RELATIONS  # default: the benchmark's schema

        return list(RELATIONS)
    return list(_RELATIONS)
