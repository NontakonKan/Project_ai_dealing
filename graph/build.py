"""Build an auditable graph from the prepared dataset, without an LLM."""
import argparse
import hashlib
import json
from pathlib import Path

from .model import Graph, validate
from .schema import EVENT_RELATIONS, GROUP_LABELS, pick

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_graph(taxonomy, users, events, chunks, provenance=None):
    graph = Graph()
    for group, label in GROUP_LABELS.items():
        for concept in taxonomy[group]:
            graph.node(concept["id"], label, **pick(concept, ("label_th", "aliases", "framework", "source", "effect")))
    for rule in taxonomy["compatibility_rules"]:
        graph.edge(rule["a"], rule["relation"], rule["b"],
                   **pick(rule, ("weight", "reason", "source")), symmetric=True,
                   assertion="unverified_taxonomy_rule", provenance="data/taxonomy.json")

    seen_users = set()
    skipped_reports = 0
    for user in users:
        uid = user["user_id"]
        if uid in seen_users:
            raise ValueError(f"Duplicate user: {uid}")
        seen_users.add(uid)
        persona = user["persona"]
        props = pick(user, ("display_name", "profile_completeness"))
        props.update(pick(user["demographic"], ("age", "gender", "seeking", "faculty", "campus")))
        props.update({f"lifestyle_{k}": v for k, v in pick(persona.get("lifestyle", {}), ("sleep", "social_energy", "weekend")).items()})
        props.update(pick(user["preferences"], ("age_range",)))
        props.update(user_id=uid, matching_consent=user["consent"]["matching"],
                     consent_updated_at=user["consent"].get("updated_at", ""),
                     data_origin="synthetic", provenance="data/mock/users.json")
        graph.node(uid, "User", **props)
        for field, relation in (("hobbies", "LIKES"), ("traits", "HAS_TRAIT"),
                                ("comm_style", "HAS_TRAIT"), ("love_language", "HAS_LOVE_LANGUAGE")):
            for item in persona.get(field, []):
                graph.edge(uid, relation, item["id"],
                           **pick(item, ("confidence", "evidence_count", "last_seen")),
                           assertion="profile_record", provenance=f"users:{uid}:persona.{field}")
        attachment = persona.get("attachment_style")
        if attachment:
            graph.edge(uid, "HAS_TRAIT", attachment["id"], **pick(attachment, ("confidence",)),
                       assertion="profile_record", provenance=f"users:{uid}:persona.attachment_style")
        for component, value in persona.get("love_components", {}).items():
            graph.edge(uid, "HAS_LOVE_COMPONENT", f"love:{component}", value=value,
                       provenance=f"users:{uid}:persona.love_components")
        if "life_satisfaction" in persona:
            graph.edge(uid, "HAS_FACTOR", "factor:life_satisfaction", value=persona["life_satisfaction"],
                       provenance=f"users:{uid}:persona.life_satisfaction")
        for field, relation in (("wants", "PREFERS"), ("avoids", "AVOIDS")):
            for item in user["preferences"].get(field, []):
                graph.edge(uid, relation, item["id"], **pick(item, ("weight", "count", "source")),
                           provenance=f"users:{uid}:preferences.{field}")
        for report in user.get("reported_traits", []):
            if report.get("usable") is not True or report.get("report_count", 0) < 3:
                skipped_reports += 1
                continue
            graph.edge(uid, "REPORTED_AS", report["id"], **pick(report, ("report_count", "usable")),
                       assertion="reported_not_verified", provenance=f"users:{uid}:reported_traits")

    seen_events = set()
    for event in events:
        eid = event["event_id"]
        if eid in seen_events:
            raise ValueError(f"Duplicate event: {eid}")
        seen_events.add(eid)
        # No raw reason or gold extraction: only observed event metadata.
        graph.edge(event["from_user"], EVENT_RELATIONS[event["type"]], event["about_user"],
                   discriminator=eid, event_id=eid, timestamp=event["timestamp"],
                   provenance="data/mock/events.jsonl")

    seen_chunks = set()
    for chunk in chunks:
        cid = chunk["chunk_id"]
        if cid in seen_chunks:
            raise ValueError(f"Duplicate chunk: {cid}")
        seen_chunks.add(cid)
        source = "source:" + chunk["source_id"]
        graph.node(source, "Source", **pick(chunk, ("source_id", "title", "doc_type", "year")),
                   provenance="data/processed/book_chunks.jsonl")
        graph.node(cid, "BookChunk", **pick(chunk, ("chunk_id", "source_id", "text", "category", "chapter",
                   "chapter_title", "section_title", "pages", "topics", "n_words", "lang")),
                   provenance="data/processed/book_chunks.jsonl")
        graph.edge(source, "HAS_CHUNK", cid, pages=chunk["pages"])
        for concept in chunk["concepts"]:
            graph.edge(cid, "ABOUT", concept, count=chunk.get("concept_counts", {}).get(concept, 1),
                       pages=chunk["pages"], assertion="keyword_tag_not_entailment",
                       provenance="pipelines/ingest/tagger.py")

    result = graph.export(provenance or {})
    stats = validate(result)
    covered = {e["target"] for e in result["relationships"] if e["type"] == "ABOUT"}
    concepts = {n["id"] for n in result["nodes"] if n["label"] in GROUP_LABELS.values()}
    stats.update(snapshot=result["snapshot"], skipped_unusable_reports=skipped_reports,
                 consented_users=sum(u["consent"]["matching"] is True for u in users),
                 concepts_without_chunks=sorted(concepts - covered),
                 warnings=[
                     "Synthetic users and events; no real-world matching accuracy is measured.",
                     "Compatibility rules are imported assumptions, not independently verified findings.",
                     "ABOUT means a keyword tag, not proof that a chunk supports a compatibility rule.",
                     "Non-consenting users remain in the mock graph for inspection; future matching must filter both users.",
                     "Report counts come from prepared profiles; independent reporters are not re-verified here.",
                 ])
    return result, stats


def load_inputs(data_dir):
    files = {"taxonomy": data_dir / "taxonomy.json", "users": data_dir / "mock/users.json",
             "events": data_dir / "mock/events.jsonl", "chunks": data_dir / "processed/book_chunks.jsonl"}
    values = {key: read_jsonl(path) if path.suffix == ".jsonl" else json.loads(path.read_text(encoding="utf-8"))
              for key, path in files.items()}
    provenance = {key: {"path": str(path.relative_to(data_dir)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for key, path in files.items()}
    return values, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    inputs, provenance = load_inputs(args.data_dir)
    _, report = build_graph(**inputs, provenance=provenance)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
