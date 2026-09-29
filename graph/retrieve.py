"""Evidence-aware Graph retrieval -> RetrievalResult for the shared RAG contract.

ABOUT edges are topical links and can only nominate source chunks. Claims that
have not been reviewed remain retrieval candidates; only human-verified claims
can be returned as graph facts. Taxonomy compatibility rules remain available
to the matching scorer, but are not presented as documentary evidence here.
Character TF-IDF supplies a lexical entry point when the query has no known
concept; source and concept edges then contribute ranking and provenance.
"""
import time
from collections import defaultdict

from pipelines.retrieval.contract import RetrievalItem, RetrievalResult

from . import concepts as concept_detector
from .schema import CLAIM_POLARITIES, CLAIM_PREDICATES
from .view import GraphView


PREDICATE_CUES = {
    "associated_with": ("สัมพันธ์", "เกี่ยวข้อง", "เกี่ยวกับ", "เชื่อมโยง"),
    "increases": ("เพิ่ม", "มากขึ้น", "สูงขึ้น", "ส่งเสริม"),
    "decreases": ("ลด", "น้อยลง", "ต่ำลง", "บรรเทา"),
    "predicts": ("ทำนาย", "คาดการณ์"),
    "causes": ("ทำให้เกิด", "ก่อให้เกิด", "เป็นสาเหตุ"),
    "prevents": ("ป้องกัน", "ยับยั้ง"),
    "differs_from": ("แตกต่าง", "ไม่เหมือน"),
    "part_of": ("เป็นส่วนหนึ่ง", "ประกอบด้วย"),
    "characterized_by": ("มีลักษณะ", "แสดงออก"),
    "depends_on": ("ขึ้นอยู่กับ", "ขึ้นกับ"),
    "supports": ("สนับสนุน", "สอดคล้อง"),
    "opposes": ("ขัดแย้ง", "ตรงข้าม"),
}


class _ChunkSearch:
    """Shared, read-only lexical index over BookChunk text and Source titles."""

    def __init__(self, graph):
        self.ids = sorted(nid for nid, node in graph.nodes.items() if node["label"] == "BookChunk")
        self.sources = {cid: graph.prop(cid, "source_id", "") for cid in self.ids}
        self.vectorizer = None
        if not self.ids:
            return
        from sklearn.feature_extraction.text import TfidfVectorizer

        small = len(self.ids) < 10
        self.vectorizer = TfidfVectorizer(
            analyzer="char", ngram_range=(2, 4), min_df=1 if small else 2,
            max_df=1.0 if small else 0.8, sublinear_tf=True, max_features=180000,
        )
        self.text_vectors = self.vectorizer.fit_transform(
            [graph.chunk_text(cid) for cid in self.ids])
        self.title_vectors = self.vectorizer.transform([
            graph.prop("source:" + self.sources[cid], "title", "") for cid in self.ids
        ])

    def scores(self, query):
        if self.vectorizer is None:
            return {}
        vector = self.vectorizer.transform([query])
        text_scores = (self.text_vectors @ vector.T).toarray().ravel()
        title_scores = (self.title_vectors @ vector.T).toarray().ravel()
        return {cid: float(text_scores[i] + 0.15 * title_scores[i])
                for i, cid in enumerate(self.ids) if text_scores[i] or title_scores[i]}


class GraphKnowledge:
    mode = "graph"
    MAX_CHUNKS_PER_SOURCE = 2
    MIN_LEXICAL_SCORE = 0.065

    def __init__(self, view: GraphView = None, use_embedding=True):
        self.g = view or GraphView.load()
        self.use_embedding = use_embedding
        self.verified_claims = self._load_verified_claims()
        self.claims_by_subject = defaultdict(list)
        for claim_id, claim in self.verified_claims.items():
            self.claims_by_subject[claim["subject_id"]].append(claim_id)

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        g = self.g
        found = concept_detector.detect(query, self.use_embedding)
        chunk_scores = defaultdict(float)
        chunk_claims = defaultdict(set)
        chunk_concepts = defaultdict(set)
        index = getattr(g, "_chunk_search", None)
        if index is None:
            index = g._chunk_search = _ChunkSearch(g)
        lexical_scores = index.scores(query)
        # Character n-grams match common Thai particles even for unrelated
        # queries. Below this floor, a text-only match is too weak to return.
        if found or max(lexical_scores.values(), default=0.0) >= self.MIN_LEXICAL_SCORE:
            chunk_scores.update(lexical_scores)
        for concept in found:
            for chunk_id, count in g.about.get(concept, []):
                chunk_concepts[chunk_id].add(concept)
                chunk_scores[chunk_id] += 0.05 * min(1.0, count / 5)

        claims = self.verified_claims
        claims_by_id = {cid: p for cid, p in claims.items()}
        claim_scores = {}
        claim_paths = {}

        # A topical link may retrieve the original passage, but never creates a
        # graph_fact. The cross-encoder downstream still decides relevance.
        candidate_ids = set()
        for concept in found:
            candidate_ids.update(g.claims_about.get(concept, []))
            candidate_ids.update(g.claims_subject.get(concept, []))
            candidate_ids.update(g.claims_object.get(concept, []))
        for claim_id in candidate_ids:
            support = g.rel(claim_id, "SUPPORTED_BY")
            for chunk_id in support:
                chunk_claims[chunk_id].add(claim_id)
                chunk_scores[chunk_id] += 0.1
            props = g.prop(claim_id, "assertion", "llm_extracted_unverified")
            if props != "human_verified" or claim_id not in claims_by_id:
                continue
            claim = claims_by_id[claim_id]
            roles_matched = int(claim["subject_id"] in found) + int(claim.get("object_concept_id") in found)
            score = 1.0 + (0.35 if roles_matched == 2 else 0.0)
            if self._predicate_matches(query, claim["predicate"]):
                score += 0.15
            claim_scores[claim_id] = score
            claim_paths[claim_id] = [claim_id]

        # A relevant passage may end before the answer. Follow document-order
        # edges one step and keep the original passage available for citation.
        chunk_neighbors = {}
        for seed in sorted(chunk_scores, key=lambda cid: -chunk_scores[cid])[:3]:
            neighbor_score = 0.5 * chunk_scores[seed]
            neighbors = set(g.rel(seed, "NEXT_CHUNK")) | set(g.previous_chunks.get(seed, ()))
            for neighbor in neighbors:
                if neighbor_score > chunk_scores[neighbor]:
                    chunk_scores[neighbor] = neighbor_score
                    chunk_neighbors[neighbor] = seed

        # Two-hop paths only join reviewed propositions with an explicit concept
        # object. Return both source-backed propositions; do not synthesize a
        # new fact whose wording has no single source passage.
        for first_id, first in claims.items():
            middle = first.get("object_concept_id")
            if not middle or first["subject_id"] not in found:
                continue
            for second_id in self.claims_by_subject.get(middle, []):
                second = claims[second_id]
                if second_id == first_id or second.get("object_concept_id") not in found:
                    continue
                path_ids = [first_id, second_id]
                score = 1.8
                if self._predicate_matches(query, first["predicate"]):
                    score += 0.1
                if self._predicate_matches(query, second["predicate"]):
                    score += 0.1
                for claim_id in path_ids:
                    claim_scores[claim_id] = max(claim_scores.get(claim_id, 0.0), score)
                    claim_paths[claim_id] = path_ids

        items = []
        for claim_id, score in claim_scores.items():
            claim = claims_by_id[claim_id]
            support_ids = sorted(g.rel(claim_id, "SUPPORTED_BY"))
            if not support_ids:
                continue
            path_ids = claim_paths[claim_id]
            path = []
            for path_claim_id in path_ids:
                p = claims_by_id[path_claim_id]
                path.append([p["subject_id"], p["predicate"],
                             p.get("object_concept_id") or p["object_text"]])
            items.append(RetrievalItem(
                claim_id, "graph_fact", self._claim_text(claim, g), round(score, 4), "graph",
                {"path": path, "claim_ids": path_ids, "evidence_chunk_ids": support_ids,
                 "source_id": claim.get("source_id"), "verification_status": "human_verified",
                 "predicate": claim["predicate"], "polarity": claim["polarity"],
                 "qualifier_text": claim.get("qualifier_text", "")},
            ))

        for chunk_id, score in chunk_scores.items():
            source_id = g.prop(chunk_id, "source_id", "")
            path = ["source:" + source_id, "HAS_CHUNK", chunk_id]
            if chunk_concepts[chunk_id]:
                path += ["ABOUT", *sorted(chunk_concepts[chunk_id])]
            items.append(RetrievalItem(
                chunk_id, "chunk", g.chunk_text(chunk_id), round(score, 4), "graph",
                {"path": path, "source_id": source_id, "pages": g.prop(chunk_id, "pages", []),
                 "concepts": sorted(chunk_concepts[chunk_id]), "claim_ids": sorted(chunk_claims[chunk_id]),
                 "adjacent_to": chunk_neighbors.get(chunk_id),
                 "claim_statuses": {cid: g.prop(cid, "assertion", "unknown")
                                    for cid in sorted(chunk_claims[chunk_id])}},
            ))

        # Compatibility edges are scoring assumptions, not knowledge-source
        # evidence. They remain in GraphView for matching, but are omitted here.
        items.sort(key=lambda item: (-item.score, item.kind != "graph_fact", item.id))
        selected, deferred, per_source = [], [], defaultdict(int)
        for item in items:
            if item.kind == "graph_fact":
                selected.append(item)
            elif per_source[item.meta["source_id"]] < self.MAX_CHUNKS_PER_SOURCE:
                selected.append(item)
                per_source[item.meta["source_id"]] += 1
            else:
                deferred.append(item)
            if len(selected) >= k:
                break
        if len(selected) < k:
            selected.extend(deferred[:k - len(selected)])
        return RetrievalResult("graph", query, selected[:max(0, k)],
                               (time.perf_counter() - t0) * 1000)

    def _load_verified_claims(self):
        return {cid: node["properties"] for cid, node in self.g.nodes.items()
                if node["label"] == "Claim"
                and node["properties"].get("assertion") == "human_verified"}

    @staticmethod
    def _predicate_matches(query, predicate):
        return any(cue in query.casefold() for cue in PREDICATE_CUES.get(predicate, ()))

    @staticmethod
    def _claim_text(claim, graph):
        subject = graph.label(claim["subject_id"])
        obj_id = claim.get("object_concept_id")
        obj = graph.label(obj_id) if obj_id else claim["object_text"]
        predicate = CLAIM_PREDICATES[claim["predicate"]]
        polarity = CLAIM_POLARITIES[claim["polarity"]]
        parts = [f"ความสัมพันธ์ที่ตรวจทานแล้ว: {subject} {predicate} {obj} ({polarity})"]
        if claim.get("qualifier_text"):
            parts.append(f"เงื่อนไขหรือขอบเขต: {claim['qualifier_text']}")
        parts.append(f"ข้อความต้นฉบับ: {claim['text']}")
        return "\n".join(parts)
