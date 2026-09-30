"""Evidence-aware Graph retrieval -> RetrievalResult for the shared RAG contract.

ABOUT edges are topical links and can only nominate source chunks. Claims
nominate original source chunks, never generated facts.
Taxonomy compatibility rules remain available to the matching scorer, but are
not presented as documentary evidence here.
Character TF-IDF supplies a lexical entry point when the query has no known
concept; source and concept edges then contribute ranking and provenance.
"""
import time
import re
from collections import defaultdict

from pipelines.retrieval.contract import RetrievalItem, RetrievalResult

from . import concepts as concept_detector
from .view import GraphView


PREDICATE_CUES = {
    "associated_with": ("สัมพันธ์", "เกี่ยวข้อง", "เกี่ยวกับ", "เชื่อมโยง"),
    "increases": ("เพิ่ม", "มากขึ้น", "สูงขึ้น", "ส่งเสริม"),
    "decreases": ("ลด", "น้อยลง", "ต่ำลง", "บรรเทา"),
    "predicts": ("ทำนาย", "พยากรณ์", "คาดการณ์"),
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

    def phrase_scores(self, queries, phrases):
        """Rank a Claim's object against the requested details, not its topic."""
        if self.vectorizer is None or not phrases:
            return {}
        ids = list(phrases)
        objects = self.vectorizer.transform([phrases[cid] for cid in ids])
        scores = (objects @ self.vectorizer.transform(queries).T).toarray().max(axis=1)
        return dict(zip(ids, map(float, scores)))


class GraphKnowledge:
    mode = "graph"
    MAX_CHUNKS_PER_SOURCE = 2
    MIN_LEXICAL_SCORE = 0.065
    MIN_OBJECT_FOCUS_SCORE = 0.08

    def __init__(self, view: GraphView = None, use_embedding=True):
        self.g = view or GraphView.load()
        self.use_embedding = use_embedding
        self.claims = self._load_claims()
        self.claims_by_subject = defaultdict(list)
        for claim_id, claim in self.claims.items():
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

        # A topical link may retrieve the original passage, but never creates a
        # graph_fact. The cross-encoder downstream still decides relevance.
        candidate_ids = set()
        for concept in found:
            candidate_ids.update(g.claims_about.get(concept, []))
            candidate_ids.update(g.claims_subject.get(concept, []))
            candidate_ids.update(g.claims_object.get(concept, []))
        requested_predicate = self._requested_predicate(query)
        from pipelines.hybrid.query_expand import variants
        queries = variants(query)
        object_scores = index.phrase_scores(queries, {
            cid: g.prop(cid, 'object_text', '') for cid in sorted(candidate_ids)
        })
        claim_bonus = defaultdict(float)
        for claim_id in sorted(candidate_ids):
            claim = g.nodes[claim_id]['properties']
            # A correlation candidate must not boost a prediction answer.
            # Topical chunk search still runs independently of this relation.
            if requested_predicate and claim['predicate'] != requested_predicate:
                continue
            support = g.rel(claim_id, "SUPPORTED_BY")
            for chunk_id in support:
                # Multiple claims from the same passage are not independent
                # evidence; extraction count must not amplify its rank.
                bonus = 0.1 + 0.6 * object_scores.get(claim_id, 0.0)
                if bonus > claim_bonus[chunk_id]:
                    chunk_scores[chunk_id] += bonus - claim_bonus[chunk_id]
                    claim_bonus[chunk_id] = bonus
                chunk_claims[chunk_id].add(claim_id)

        # A two-edge chain can bring both original passages into context. The
        # chain itself is only a navigation path, not a new factual proposition.
        two_hop_paths = defaultdict(set)
        for first_id, first in self.claims.items():
            middle = first.get("object_concept_id")
            if (not middle or first["subject_id"] not in found or requested_predicate
                    or first["polarity"] != "affirmed"):
                continue
            for second_id in self.claims_by_subject.get(middle, []):
                second = self.claims[second_id]
                if (second_id == first_id or second.get("object_concept_id") not in found
                        or second["polarity"] != "affirmed"):
                    continue
                path = (first_id, second_id)
                for claim_id in path:
                    for chunk_id in g.rel(claim_id, "SUPPORTED_BY"):
                        chunk_scores[chunk_id] = max(chunk_scores[chunk_id], 1.8)
                        chunk_claims[chunk_id].add(claim_id)
                        two_hop_paths[chunk_id].add(path)

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

        # The document introduction can contain the definition/context needed
        # to interpret a later quote. Follow Source/HAS_CHUNK rather than
        # treating an isolated research result as the whole source.
        source_context = defaultdict(set)
        for chunk_id, claim_ids in list(chunk_claims.items()):
            if not claim_ids:
                continue
            source = 'source:' + g.prop(chunk_id, 'source_id', '')
            intro = min(g.rel(source, 'HAS_CHUNK'), default=None)
            if intro and intro != chunk_id:
                source_context[intro].add(chunk_id)
                chunk_scores[intro] = max(chunk_scores[intro], 0.5 * chunk_scores[chunk_id])

        items = []
<<<<<<< HEAD
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
                 "evidence_paths": [[claim['subject_id'], '<-SUBJECT-', claim_id,
                                     'SUPPORTED_BY', chunk_id, '<-HAS_CHUNK-',
                                     'source:' + g.prop(chunk_id, 'source_id', '')]
                                    for chunk_id in support_ids],
                 "source_id": claim.get("source_id"), "verification_status": "human_verified",
                 "predicate": claim["predicate"], "polarity": claim["polarity"],
                 "qualifier_text": claim.get("qualifier_text", "")},
            ))

        if hasattr(g, "prefetch_nodes"):   # Neo4j: ดึง property ของ chunk ทั้งหมดที่ได้คะแนนใน Cypher เดียว
            g.prefetch_nodes(list(chunk_scores))
=======
>>>>>>> origin/main
        has_claim_support = any(chunk_claims.values())
        # Common Thai particles alone must not restrict a definition question
        # to the few chunks that happen to have a Claim for this concept.
        best_object_score = max((
            object_scores.get(cid, 0.0) for ids in chunk_claims.values() for cid in ids
        ), default=0.0)
        detail_terms = self._detail_terms(queries, found)
        detail_scores = index.phrase_scores([' '.join(sorted(detail_terms))], {
            cid: g.prop(cid, 'object_text', '')
            for ids in chunk_claims.values() for cid in ids
        }) if detail_terms else {}
        detail_match = max(detail_scores.values(), default=0.0) > 0
        focus_claim_support = has_claim_support and (
            best_object_score >= self.MIN_OBJECT_FOCUS_SCORE or detail_match)
        for chunk_id, score in chunk_scores.items():
            # When the query also touches a Claim's object, keep this channel within
            # its graph neighbourhood. Filling a large RRF pool with unrelated
            # lexical matches otherwise doubles Dense votes and buries the
            # very evidence the graph recovered. Other questions about the
            # concept retain the general search: the Claim set is not exhaustive.
            neighbor_of = chunk_neighbors.get(chunk_id)
            if focus_claim_support and not (chunk_claims[chunk_id]
                    or chunk_id in source_context
                    or (neighbor_of and chunk_claims[neighbor_of])):
                continue
            source_id = g.prop(chunk_id, "source_id", "")
            path = ["source:" + source_id, "HAS_CHUNK", chunk_id]
            if chunk_concepts[chunk_id]:
                path += ["ABOUT", *sorted(chunk_concepts[chunk_id])]
            text, span = self._source_excerpt(chunk_id, chunk_claims[chunk_id])
            quote_ids = sorted(chunk_claims[chunk_id])
            # A source excerpt is a different context unit from the complete
            # Dense chunk. Its existing Claim ID resolves provenance in the
            # app and prevents Dense-first deduplication replacing the excerpt.
            item_id = quote_ids[0] if quote_ids else chunk_id
            items.append(RetrievalItem(
                item_id, "chunk", text, round(score, 4), "graph",
                {"path": path, "source_id": source_id, "pages": g.prop(chunk_id, "pages", []),
                 "chunk_id": chunk_id, "category": g.prop(chunk_id, "category", ""),
                 "source_text_range": span,
                 "concepts": sorted(chunk_concepts[chunk_id]), "claim_ids": sorted(chunk_claims[chunk_id]),
                 "evidence_paths": [[g.prop(cid, 'subject_id'), '<-SUBJECT-', cid,
                                     'SUPPORTED_BY', chunk_id]
                                    for cid in sorted(chunk_claims[chunk_id])],
                 "adjacent_to": chunk_neighbors.get(chunk_id),
                 "source_context_for": sorted(source_context[chunk_id]),
                 "two_hop_paths": [list(path) for path in sorted(two_hop_paths[chunk_id])]},
            ))

        # Compatibility edges are scoring assumptions, not knowledge-source
        # evidence. They remain in GraphView for matching, but are omitted here.
        items.sort(key=lambda item: (-item.score, item.id))
        selected, deferred, per_source = [], [], defaultdict(int)
        for item in items:
            if per_source[item.meta["source_id"]] < self.MAX_CHUNKS_PER_SOURCE:
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

    def _source_excerpt(self, chunk_id, claim_ids):
        """Return one contiguous source span covering matched quote paragraphs.

        Rerankers truncate long mixed-topic chunks. A source excerpt retains
        the entire quoted evidence (including conditions and negations), with
        offsets into the unchanged BookChunk. No generated proposition or
        synthetic joins are sent as evidence.
        """
        text = self.g.chunk_text(chunk_id)
        spans = []
        for claim_id in sorted(claim_ids):
            quote = self.g.prop(claim_id, 'text', '')
            start = text.find(quote) if quote else -1
            if start >= 0:
                spans.append((start, start + len(quote)))
        start = min(s[0] for s in spans) if spans else 0
        end = max(s[1] for s in spans) if spans else len(text)
        # Preserve nearby conditions/negations in the same source paragraph.
        # If OCR has no line breaks, retain that whole paragraph even if long.
        start = text.rfind('\n', 0, start) + 1
        paragraph_end = text.find('\n', end)
        end = paragraph_end if paragraph_end >= 0 else len(text)
        return text[start:end], [start, end]

    def _load_claims(self):
        return {cid: node["properties"] for cid, node in self.g.nodes.items()
                if node["label"] == "Claim"}

    def _detail_terms(self, queries, concepts):
        """Distinguish requested details from a concept-only definition query."""
        from pythainlp.corpus import thai_stopwords
        from pythainlp.tokenize import word_tokenize

        topic_terms = {'attachment', 'รูปแบบความผูกพัน', 'เป็นอย่างไร', 'คืออะไร'}
        for concept in concepts:
            topic_terms.add(self.g.prop(concept, 'label_th', ''))
            topic_terms.update(self.g.prop(concept, 'aliases', []))
            topic_terms.add(concept.split(':', 1)[-1].replace('_', ' '))
        topic_terms.update(key for key, cid in concept_detector.EXTRA_KEYS.items()
                           if cid in concepts)
        # Duration/frequency words carry the requested meaning in questions
        # such as "why does the negative feeling last so long?".
        stopwords = (thai_stopwords() - {'นาน', 'ช้า', 'เร็ว', 'บ่อย', 'ซ้ำ'}) | {
            'อย่างไร', 'อะไร', 'แบบ', 'รูปแบบ', 'ทำให้',
        }
        details = set()
        for query in queries:
            text = query.casefold()
            for term in sorted(filter(None, topic_terms), key=len, reverse=True):
                text = re.sub(re.escape(term.casefold()), ' ', text)
            details.update(token for token in word_tokenize(text, engine='newmm')
                           if len(token) >= 3 and token not in stopwords
                           and any(char.isalnum() for char in token))
        return details

    @staticmethod
    def _requested_predicate(query):
        for predicate in ('predicts', 'causes', 'prevents'):
            if any(cue in query.casefold() for cue in PREDICATE_CUES[predicate]):
                return predicate
        return None
