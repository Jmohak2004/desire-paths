"""Desire Paths: learned route templates on SelfGraph / HydraDB. Agent cost per task falls as your graph is used."""
from .backend import GraphBackend, make_selfgraph, selfgraph_schema
from .routes import Candidate, Edge, RouteLibrary, RouteTemplate, Trace, candidate_paths, verified_paths
from .schema import get_relations, set_relations

__version__ = "0.1.0"
__all__ = ["GraphBackend", "make_selfgraph", "selfgraph_schema", "Candidate", "Edge", "RouteLibrary",
           "RouteTemplate", "Trace", "candidate_paths", "verified_paths", "get_relations", "set_relations"]
