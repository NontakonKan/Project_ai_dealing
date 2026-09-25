"""Versioned, transactional imports scoped to this project's graph only."""
import os
from collections import defaultdict

from .model import validate
from .schema import CONCEPT_LABELS, DATASET

CONSTRAINTS = (
    "CREATE CONSTRAINT dealing_entity_key IF NOT EXISTS FOR (n:DealingEntity) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT dealing_dataset_id IF NOT EXISTS FOR (n:DealingDataset) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX dealing_entity_lookup IF NOT EXISTS FOR (n:DealingEntity) ON (n.dataset, n.snapshot, n.id)",
)


def connect():
    from neo4j import GraphDatabase
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("Set NEO4J_PASSWORD before connecting to Neo4j")
    return GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:17687"),
        auth=(os.environ.get("NEO4J_USERNAME", "neo4j"), password),
    )


def database():
    return os.environ.get("NEO4J_DATABASE", "neo4j")


def _batches(rows, size=500):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def _write_snapshot(tx, graph):
    dataset, snapshot = graph["dataset"], graph["snapshot"]
    # Serialize publishers of this dataset before writing the active pointer.
    tx.run("MERGE (d:DealingDataset {id:$dataset}) SET d.lock = coalesce(d.lock, 0) + 1",
           dataset=dataset).consume()
    groups, edges = defaultdict(list), defaultdict(list)
    key = lambda node_id: f"{dataset}|{snapshot}|{node_id}"
    for node in graph["nodes"]:
        props = dict(node["properties"])
        # Human-readable fallback caption for Neo4j Browser and graph exports.
        props["display_name"] = (props.get("display_name") or props.get("label_th")
                                 or props.get("section_title") or props.get("source_id") or node["id"])
        groups[node["label"]].append({"key": key(node["id"]), "properties": {
            **props, "key": key(node["id"]), "id": node["id"],
            "dataset": dataset, "snapshot": snapshot}})
    for edge in graph["relationships"]:
        edges[edge["type"]].append({"source": key(edge["source"]), "target": key(edge["target"]),
            "id": edge["id"], "properties": {**edge["properties"], "id": edge["id"],
                                             "dataset": dataset, "snapshot": snapshot}})
    # Labels/types are allowlisted by validate(); all input values use parameters.
    for label, rows in groups.items():
        concept = ":Concept" if label in CONCEPT_LABELS else ""
        for batch in _batches(rows):
            tx.run(f"UNWIND $rows AS row MERGE (n:DealingEntity {{key:row.key}}) "
                   f"SET n:{label}{concept} SET n = row.properties", rows=batch).consume()
    for kind, rows in edges.items():
        for batch in _batches(rows):
            tx.run("UNWIND $rows AS row MATCH (a:DealingEntity {key:row.source}), "
                   "(b:DealingEntity {key:row.target}) "
                   f"MERGE (a)-[r:{kind} {{id:row.id}}]->(b) SET r = row.properties", rows=batch).consume()
    counts = _counts(tx, dataset, snapshot)
    expected = {"nodes": len(graph["nodes"]), "relationships": len(graph["relationships"])}
    if counts != expected:
        raise ValueError(f"Neo4j count mismatch: {counts} != {expected}")
    tx.run("MATCH (d:DealingDataset {id:$dataset}) "
           "SET d.active_snapshot=$snapshot, d.node_count=$nodes, "
           "d.relationship_count=$relationships, d.format_version=$version",
           dataset=dataset, snapshot=snapshot, version=graph["format_version"], **counts).consume()
    return {**counts, "dataset": dataset, "snapshot": snapshot}


def _counts(tx, dataset, snapshot):
    nodes = tx.run("MATCH (n:DealingEntity {dataset:$dataset, snapshot:$snapshot}) RETURN count(n) AS n",
                   dataset=dataset, snapshot=snapshot).single()["n"]
    relationships = tx.run(
        "MATCH (:DealingEntity {dataset:$dataset, snapshot:$snapshot})-[r]->"
        "(:DealingEntity {dataset:$dataset, snapshot:$snapshot}) RETURN count(r) AS n",
        dataset=dataset, snapshot=snapshot).single()["n"]
    return {"nodes": nodes, "relationships": relationships}


def import_graph(driver, graph, db="neo4j"):
    validate(graph)
    driver.verify_connectivity()
    with driver.session(database=db) as session:
        for query in CONSTRAINTS:
            session.run(query).consume()
        return session.execute_write(_write_snapshot, graph)


def read_graph(driver, query, parameters=None, db="neo4j"):
    """Run a supplied graph exploration query against one consistent active snapshot."""
    def read(tx):
        row = tx.run("MATCH (d:DealingDataset {id:$dataset}) RETURN d.active_snapshot AS snapshot",
                     dataset=DATASET).single()
        if not row:
            raise ValueError("No graph imported yet")
        params = {**(parameters or {}), "dataset": DATASET, "snapshot": row["snapshot"]}
        return [record.data() for record in tx.run(query, **params)]
    with driver.session(database=db) as session:
        return session.execute_read(read)
