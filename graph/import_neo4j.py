"""Build from prepared data and import directly into Neo4j without intermediate files."""
import argparse
import json
from pathlib import Path

from .build import ROOT, build_graph, load_inputs, read_jsonl
from .neo4j_store import connect, database, import_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--claims", type=Path, help="Explicit source-bound Claim JSONL for this import")
    parser.add_argument("--trial", action="store_true", help="Store snapshot without changing active graph")
    args = parser.parse_args()
    inputs, provenance = load_inputs(args.data_dir)
    if args.claims:
        inputs["claims"] = read_jsonl(args.claims)
    graph, _ = build_graph(**inputs, provenance=provenance)
    with connect() as driver:
        result = import_graph(driver, graph, database(), activate=not args.trial)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
