"""Portable graph format, stable identifiers and strict structural validation."""
import hashlib
import json
import math
import re
from collections import Counter

from .schema import (CLAIM_ASSERTIONS, CLAIM_POLARITIES, CLAIM_PREDICATES, DATASET,
                     FORMAT_VERSION, LABELS, RELATIONS, RULE_RELATIONS)


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
    supported = set()
    subjects, objects, about_concepts = {}, {}, {}
    next_chunks, previous_chunks = set(), set()
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
        if e["type"] == "SUPPORTED_BY":
            claim, chunk = nodes[e["source"]]["properties"], nodes[e["target"]]["properties"]
            quote = claim.get("text")
            if (not isinstance(quote, str) or not quote or quote not in chunk.get("text", "")
                    or p.get("evidence") != quote or claim.get("assertion") not in CLAIM_ASSERTIONS
                    or p.get("assertion") != "exact_source_quote"
                    or claim.get("chunk_id") != e["target"]):
                raise ValueError("Claim lacks exact source evidence or extraction status")
            if e["source"] in supported:
                raise ValueError("Claim must link to exactly one source chunk")
            supported.add(e["source"])
        if e["type"] == "NEXT_CHUNK":
            left, right = nodes[e["source"]]["properties"], nodes[e["target"]]["properties"]
            left_pos = re.fullmatch(r"(.*_c)(\d+)", e["source"])
            right_pos = re.fullmatch(r"(.*_c)(\d+)", e["target"])
            if (not left_pos or not right_pos or left.get("source_id") != right.get("source_id")
                    or left_pos.group(1) != right_pos.group(1)
                    or int(right_pos.group(2)) != int(left_pos.group(2)) + 1
                    or p.get("assertion") != "document_order"
                    or e["source"] in next_chunks or e["target"] in previous_chunks):
                raise ValueError("Invalid document-order relationship")
            next_chunks.add(e["source"])
            previous_chunks.add(e["target"])
        if e["type"] == "SUBJECT":
            if e["source"] in subjects:
                raise ValueError("Claim must have exactly one subject")
            subjects[e["source"]] = e["target"]
        if e["type"] == "OBJECT":
            if e["source"] in objects:
                raise ValueError("Claim can have at most one concept object")
            objects[e["source"]] = e["target"]
        if e["type"] == "ABOUT" and nodes[e["source"]]["label"] == "Claim":
            about_concepts.setdefault(e["source"], set()).add(e["target"])
        for key in ("confidence", "weight"):
            if key in p and (type(p[key]) not in (int, float) or not 0 <= p[key] <= 1):
                raise ValueError(f"Invalid {key}: {e['id']}")
        if e["type"] == "REPORTED_AS" and (p.get("usable") is not True or p.get("report_count", 0) < 3):
            raise ValueError("Unusable report reached graph")
        if e["type"] in RULE_RELATIONS and p.get("assertion") != "unverified_taxonomy_rule":
            raise ValueError("Compatibility rule must retain its unverified status")
    for nid, node in nodes.items():
        if node["label"] != "Claim":
            continue
        props = node["properties"]
        if nid not in supported:
            raise ValueError("Claim must link to source evidence")
        if (not isinstance(props.get("concept_ids"), list)
                or any(not isinstance(concept, str) for concept in props["concept_ids"])
                or len(set(props["concept_ids"])) != len(props["concept_ids"])
                or set(props["concept_ids"]) != about_concepts.get(nid, set())
                or props.get("subject_id") not in props["concept_ids"]):
            raise ValueError("Claim concept links do not match its explicit ABOUT edges")
        if nid not in subjects or subjects[nid] != props.get("subject_id"):
            raise ValueError("Claim subject edge does not match its structured subject")
        if props.get("object_concept_id"):
            if objects.get(nid) != props["object_concept_id"]:
                raise ValueError("Claim object edge does not match its structured object")
        elif nid in objects:
            raise ValueError("Claim has an object edge without an object concept")
        if props.get("predicate") not in CLAIM_PREDICATES:
            raise ValueError("Claim has an unknown predicate")
        if props.get("polarity") not in CLAIM_POLARITIES:
            raise ValueError("Claim has an unknown polarity")
        quote, object_text = props.get("text", ""), props.get("object_text", "")
        qualifier = props.get("qualifier_text", "")
        if (not isinstance(object_text, str) or not 2 <= len(object_text) <= 240 or object_text not in quote
                or not isinstance(qualifier, str) or len(qualifier) > 400
                or (qualifier and qualifier not in quote)):
            raise ValueError("Claim structure must preserve exact source phrases")
        from .claims import _predicate_evidenced
        if not _predicate_evidenced(quote, props['predicate'], object_text):
            raise ValueError('Strong claim predicate must be explicit beside its object')
        if props["assertion"] == "human_verified":
            reviewer, reviewed_at = props.get("reviewed_by"), props.get("reviewed_at")
            if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reviewed_at, str):
                raise ValueError("Human-verified claims require reviewer metadata")
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise ValueError("Claim review timestamp must be ISO 8601") from exc
            if timestamp.tzinfo is None:
                raise ValueError("Claim review timestamp must include a timezone")
        elif props.get("reviewed_by") or props.get("reviewed_at"):
            raise ValueError("Unverified claims cannot carry reviewer metadata")
        expected_id = "claim:" + digest([
            props.get("chunk_id"), props.get("chunk_hash"), quote,
            sorted(props["concept_ids"]), props.get("subject_id"), props.get("predicate"),
            props.get("object_concept_id") or "", object_text, props.get("polarity"), qualifier,
        ])[:24]
        if nid != expected_id:
            raise ValueError("Claim ID does not match its structured evidence")
    if graph.get("snapshot") != content_hash(graph):
        raise ValueError("Graph content hash mismatch; rebuild before import")
    return {"nodes": len(nodes), "relationships": len(edges),
            "nodes_by_label": dict(sorted(Counter(n["label"] for n in nodes.values()).items())),
            "relationships_by_type": dict(sorted(Counter(e["type"] for e in graph["relationships"]).items()))}
