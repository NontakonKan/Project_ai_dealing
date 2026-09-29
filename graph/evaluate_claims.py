"""Reproducible graph-only pilot A/B. Gold chunks are targeted, not exhaustive relevance labels."""
import argparse
import json
import re
import statistics
import time
from pathlib import Path

from .build import ROOT, build_graph, load_inputs, read_jsonl
from .claims import DEFAULT_MODEL, _chat
from .retrieve import GraphKnowledge
from .view import GraphView

CASES = [
    ('secure', 'secure attachment มองตนเองและผู้อื่นอย่างไร', ['web_chula_attachment_s00_c02']),
    ('caregiver', 'ความผูกพันแบบมั่นคง secure ในทารกสัมพันธ์กับการดูแลอย่างไร',
     ['web_chula_attachment_s00_c00', 'web_chula_attachment_s00_c01']),
    ('intimacy', 'ความใกล้ชิดเกี่ยวข้องกับมิติหลีกเลี่ยงอย่างไร', ['web_chula_attachment_s00_c02']),
    ('gaslighting', 'gaslighting พบได้เฉพาะคู่รักหรือไม่', ['web_chula_gaslighting_s00_c00']),
    ('paraphrase', 'คนรักทำให้เราสงสัยความจำตัวเองเรียกว่าอะไร', ['web_chula_gaslighting_s00_c00']),
    ('unrelated', 'ราคาทองวันนี้เท่าไร', []),
]


def answer(question, items):
    # Isolate graph evidence: exclude unverified matching rules from this experiment.
    passages = {it.id: it.text for it in items if it.kind == 'chunk'}
    if not passages:
        return {'answer': 'ไม่มีหลักฐานจากการค้น', 'evidence': [], 'quote_checks': []}
    schema = {'type': 'object', 'required': ['answer', 'evidence'], 'properties': {
        'answer': {'type': 'string'}, 'evidence': {'type': 'array', 'items': {
            'type': 'object', 'required': ['chunk_id', 'quote'], 'properties': {
                'chunk_id': {'type': 'string', 'enum': list(passages)}, 'quote': {'type': 'string'}}}}}}
    result = _chat(DEFAULT_MODEL, [
        {'role': 'system', 'content': 'ตอบภาษาไทยจากข้อความต้นฉบับที่ให้เท่านั้น ห้ามเดา '
         'รักษาคำว่าอาจ เงื่อนไขและกลุ่มประชากร ถ้าไม่มีหลักฐานให้บอกไม่มีข้อมูล '
         'evidence ต้องคัดข้อความตรงต้นฉบับ พร้อม chunk_id ส่ง JSON ตาม schema: ' + json.dumps(schema)},
        {'role': 'user', 'content': json.dumps({'question': question, 'passages': passages}, ensure_ascii=False)}], schema)
    if result.metrics.get('truncated'):
        raise ValueError('Answer truncated')
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', result.text.strip())
    obj = json.loads(raw)
    obj['quote_checks'] = [bool(e.get('quote')) and e['quote'] in passages.get(e.get('chunk_id'), '')
                           for e in obj.get('evidence', [])]
    return obj


def evaluate(claims, generate=False):
    inputs, provenance = load_inputs(ROOT / 'data')
    inputs.pop('claims', None)
    base, _ = build_graph(**inputs, provenance=provenance)
    trial, stats = build_graph(**inputs, provenance=provenance, claims=claims)
    views = {'baseline': GraphView(base), 'claims': GraphView(trial)}
    rows = []
    for name, question, gold in CASES:
        row = {'case': name, 'question': question, 'target_chunks': gold}
        for variant, view in views.items():
            result = GraphKnowledge(view, use_embedding=False).retrieve(question, k=8)
            ids = [it.id for it in result.items]
            positions = [ids.index(c) + 1 for c in gold if c in ids]
            row[variant] = {'ids': ids, 'hit_at_8': bool(positions) if gold else None,
                            'reciprocal_rank': 1 / min(positions) if positions else 0,
                            'target_recall_at_8': len(positions) / len(gold) if gold else None,
                            'latency_ms': result.latency_ms}
            if generate and name in {'secure', 'gaslighting'}:
                row[variant]['answer_sample'] = answer(question, result.items)
        rows.append(row)
    from .scorer import pair
    pairs = [('U001', 'U002'), ('U003', 'U004'), ('U010', 'U011')]
    unchanged = all(pair(views['baseline'], a, b) == pair(views['claims'], a, b) for a, b in pairs)
    summary = {}
    for variant in views:
        scored = [r[variant] for r in rows if r['target_chunks']]
        summary[variant] = {'hit_at_8': sum(r['hit_at_8'] for r in scored) / len(scored),
                            'mrr_at_8': sum(r['reciprocal_rank'] for r in scored) / len(scored)}
    return {'model': DEFAULT_MODEL, 'accepted_claims': len(claims), 'graph_stats': stats,
            'matching_unchanged_for_3_pairs': unchanged, 'summary': summary, 'cases': rows,
            'limitations': ['Small targeted pilot, not held-out benchmark',
                'Real alias concept detection; embeddings disabled to isolate graph changes',
                'No ChromaDB or production RAG gates used',
                'Exact quote checks do not establish semantic correctness',
                'Generated answers use Qwen3.5 for both variants, not production answer-model configuration']}


def retrieval_benchmark(k=8):
    """Read-only comparison on the existing question set; no model answers or output files."""
    from pipelines.hybrid.context import HybridContext
    from pipelines.hybrid.knowledge_eval import _relevant
    from pipelines.hybrid.retrievers import DenseKnowledge, HybridKnowledge
    from pipelines.llm.bench.datasets import rag
    from .concepts import by_alias

    ctx = HybridContext()
    view = ctx.graph
    graph = GraphKnowledge(view, use_embedding=False)
    # Keep the same text index and source-diversity logic, removing only the
    # graph edges used for topical and document-order traversal. This separates
    # lexical gains from gains due to graph relationships.
    inputs, provenance = load_inputs(ROOT / 'data')
    raw, _ = build_graph(**inputs, provenance=provenance)
    no_topic_order = {**raw, 'relationships': [edge for edge in raw['relationships']
                                             if edge['type'] not in {'ABOUT', 'NEXT_CHUNK'}]}
    lexical_ablation = GraphKnowledge(GraphView(no_topic_order), use_embedding=False)
    dense = DenseKnowledge(ctx)
    hybrid = HybridKnowledge(ctx)
    hybrid.graph.use_embedding = False
    questions = rag()
    answerable = [q for q in questions if q['answerable']]
    unanswerable = [q for q in questions if not q['answerable']]

    def legacy(query):
        scores = {}
        for concept in by_alias(query):
            for chunk_id, count in view.about.get(concept, []):
                scores[chunk_id] = scores.get(chunk_id, 0) + count / 10
        return [chunk_id for chunk_id in sorted(scores, key=lambda cid: (-min(1.0, scores[cid]), cid))[:k]]

    retrievers = {
        'legacy_tag_graph': legacy,
        'graph_without_topic_order_edges': lambda query: [item.id for item in lexical_ablation.retrieve(query, k).items],
        'dense': lambda query: [item.id for item in dense.retrieve(query, k).items],
        'graph': lambda query: [item.id for item in graph.retrieve(query, k).items],
        'hybrid_rrf': lambda query: [item.id for item in hybrid.retrieve(query, k).items],
    }
    results, hits_by_mode = {}, {}
    for name, retrieve in retrievers.items():
        hit = reciprocal_rank = 0.0
        hits = {}
        elapsed_ms = []
        for q in answerable:
            started = time.perf_counter()
            ids = retrieve(q['question'])
            elapsed_ms.append((time.perf_counter() - started) * 1000)
            ranks = [i + 1 for i, cid in enumerate(ids)
                     if _relevant(view.chunk_text(cid), q['expected_keywords'])]
            hits[q['question']] = bool(ranks)
            if ranks:
                hit += 1
                reciprocal_rank += 1 / ranks[0]
        hits_by_mode[name] = hits
        warm_ms = sorted(elapsed_ms[1:]) or sorted(elapsed_ms)
        results[name] = {f'hit_at_{k}': round(hit / len(answerable), 3),
                         f'mrr_at_{k}': round(reciprocal_rank / len(answerable), 3),
                         'warm_p50_ms': round(statistics.median(warm_ms), 1),
                         'warm_p95_ms': round(warm_ms[int(0.95 * (len(warm_ms) - 1))], 1),
                         'empty_on_unanswerable': sum(not retrieve(q['question']) for q in unanswerable)}
    graph_hits, dense_hits = hits_by_mode['graph'], hits_by_mode['dense']
    pilot_edge_recovery = []
    for name, question, targets in CASES:
        if not targets:
            continue
        full = {item.id for item in graph.retrieve(question, k).items}
        ablated = {item.id for item in lexical_ablation.retrieve(question, k).items}
        if any(target in full and target not in ablated for target in targets):
            pilot_edge_recovery.append(name)
    return {'questions': len(questions), 'answerable': len(answerable),
            'unanswerable': len(unanswerable), 'k': k, 'metrics': results,
            'pilot_edge_recovery': pilot_edge_recovery,
            'graph_hits_dense_misses': [q for q in graph_hits if graph_hits[q] and not dense_hits[q]],
            'dense_hits_graph_misses': [q for q in dense_hits if dense_hits[q] and not graph_hits[q]],
            'limitations': ['Relevance is a keyword heuristic, not human-reviewed answer quality.',
                            'The question set was used during development, so it is not a held-out test.',
                            'The application relevance and answer-verification gates are not run here.',
                            'Claims without human review remain source chunks, not graph facts.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claims', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--retrieval-benchmark', action='store_true',
                        help='Compare legacy Graph, Dense, current Graph and Hybrid on existing questions')
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    if args.retrieval_benchmark:
        if args.claims or args.output or args.generate:
            parser.error('--retrieval-benchmark does not use --claims, --output or --generate')
        print(json.dumps(retrieval_benchmark(), ensure_ascii=False, indent=2))
        return
    if not args.claims or not args.output:
        parser.error('Claim evaluation requires --claims and --output')
    report = evaluate(read_jsonl(args.claims), args.generate)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
