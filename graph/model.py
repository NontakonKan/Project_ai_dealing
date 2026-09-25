"""Portable graph format, stable identifiers and strict structural validation."""
import hashlib
import json
import math
from collections import Counter

from .schema import DATASET, FORMAT_VERSION, LABELS, RELATIONS, RULE_RELATIONS


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def content_hash(graph):
    return digest({k: graph[k] for k in ("format_version", "dataset", "nodes", "relationships")})


class Graph:
    def __init__(self):
        self.nodes = {}
        self.relationships = {}

    def node(self, node_id, label, **properties):
        row = {"id": node_id, "label": label, "properties": properties}
        old = self.nodes.get(node_id)
        if old is not None and old != row:
            raise ValueError(f"Conflicting node: {node_id}")
        self.nodes[node_id] = row

    def edge(self, source_id, relation, target_id, *, discriminator="", **properties):
        edge_id = "edge:" + digest([source_id, relation, target_id, discriminator])[:24]
        row = {"id": edge_id, "source": source_id, "target": target_id,
               "type": relation, "properties": properties}
        old = self.relationships.get(edge_id)
        if old is not None and old != row:
            raise ValueError(f"Conflicting relationship: {edge_id}")
        self.relationships[edge_id] = row

    def export(self, provenance):
        graph = {
            "format_version": FORMAT_VERSION, "dataset": DATASET,
            "nodes": sorted(self.nodes.values(), key=lambda n: n["id"]),
            "relationships": sorted(self.relationships.values(), key=lambda e: e["id"]),
            "provenance": provenance,
        }
        graph["snapshot"] = content_hash(graph)
        validate(graph)
        return graph


def _properties(props):
    if not isinstance(props, dict):
        raise ValueError("Properties must be an object")
    for key, value in props.items():
        if key.startswith("_") or key in {"gold_extracted", "ground_truth", "raw_reason", "key", "snapshot", "dataset", "id"}:
            raise ValueError(f"Forbidden graph property: {key}")
        values = value if isinstance(value, list) else [value]
        if any(type(v) not in (str, int, float, bool) for v in values):
            raise ValueError(f"Unsupported Neo4j property: {key}")
        if isinstance(value, list) and len({type(v) for v in values}) > 1:
            raise ValueError(f"Mixed array types: {key}")
        if any(isinstance(v, float) and not math.isfinite(v) for v in values):
            raise ValueError(f"Non-finite property: {key}")


def validate(graph):
    if graph["format_version"] != FORMAT_VERSION or graph["dataset"] != DATASET:
        raise ValueError("Unsupported graph format/dataset")
    nodes = {}
    for n in graph["nodes"]:
        if not isinstance(n["id"], str) or not n["id"] or n["id"] in nodes:
            raise ValueError(f"Invalid/duplicate node ID: {n['id']}")
        if n["label"] not in LABELS:
            raise ValueError(f"Unknown label: {n['label']}")
        _properties(n["properties"])
        nodes[n["id"]] = n
    edges = set()
    for e in graph["relationships"]:
        if not isinstance(e["id"], str) or not e["id"] or e["id"] in edges:
            raise ValueError(f"Invalid/duplicate edge ID: {e['id']}")
        edges.add(e["id"])
        if e["type"] not in RELATIONS:
            raise ValueError(f"Unknown relation: {e['type']}")
        if e["source"] not in nodes or e["target"] not in nodes:
            raise ValueError(f"Dangling relationship: {e['id']}")
        domain, range_ = RELATIONS[e["type"]]
        if nodes[e["source"]]["label"] not in domain or nodes[e["target"]]["label"] not in range_:
            raise ValueError(f"Wrong domain/range: {e['id']}")
        p = e["properties"]
        _properties(p)
        for key in ("confidence", "weight"):
            if key in p and (type(p[key]) not in (int, float) or not 0 <= p[key] <= 1):
                raise ValueError(f"Invalid {key}: {e['id']}")
        if e["type"] == "REPORTED_AS" and (p.get("usable") is not True or p.get("report_count", 0) < 3):
            raise ValueError("Unusable report reached graph")
        if e["type"] in RULE_RELATIONS and p.get("assertion") != "unverified_taxonomy_rule":
            raise ValueError("Compatibility rule must retain its unverified status")
    if graph.get("snapshot") != content_hash(graph):
        raise ValueError("Graph content hash mismatch; rebuild before import")
    return {"nodes": len(nodes), "relationships": len(edges),
            "nodes_by_label": dict(sorted(Counter(n["label"] for n in nodes.values()).items())),
            "relationships_by_type": dict(sorted(Counter(e["type"] for e in graph["relationships"]).items()))}
