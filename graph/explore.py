"""Inspect nodes, relationships and evidence in the active Neo4j graph."""
import argparse
import json

from .neo4j_store import connect, database, read_graph
from .queries import QUERIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=QUERIES)
    parser.add_argument("--user-id")
    parser.add_argument("--other-id")
    parser.add_argument("--concept-id")
    args = parser.parse_args()
    required = {"profile": ["user_id"], "events": ["user_id"],
                "shared": ["user_id", "other_id"], "rule-paths": ["user_id", "other_id"],
                "pair-features": ["user_id", "other_id"],
                "chunks": ["concept_id"]}.get(args.view, [])
    for field in required:
        if not getattr(args, field):
            parser.error(f"{args.view} requires --{field.replace('_', '-')}")
    params = {key: getattr(args, key) for key in ("user_id", "other_id", "concept_id")}
    with connect() as driver:
        result = read_graph(driver, QUERIES[args.view], params, database())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
