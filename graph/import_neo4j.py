"""Build from prepared data and import directly into Neo4j without intermediate files."""
import argparse
import json
from pathlib import Path

from .build import ROOT, build_graph, load_inputs
from .neo4j_store import connect, database, import_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    inputs, provenance = load_inputs(args.data_dir)
    graph, _ = build_graph(**inputs, provenance=provenance)
    with connect() as driver:
        result = import_graph(driver, graph, database())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
