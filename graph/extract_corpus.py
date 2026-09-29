"""Resume source-bound Claim extraction across the complete prepared corpus.

The SQLite cache is the checkpoint. A failed or interrupted run leaves the
published Claim file unchanged; rerunning reuses completed chunks.
"""

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from .build import PACKAGED_CLAIMS, ROOT, build_graph, load_inputs, read_jsonl
from .claim_cache import ClaimCache, model_revision
from .claims import (DEFAULT_MODEL, catalog, claim_identifier, mentioned,
                     source_passages, validate_claim)
from .model import digest

PACKAGED_SELECTION = ROOT / 'graph/experiments/claims_corpus_selection.json'


def _atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', suffix='.tmp',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _eligible(chunk, concepts):
    """Use the extractor's own passage and lexical rules, not ingest tags."""
    return any(mentioned(passage, concept)
               for passage in source_passages(chunk['text']).values()
               for concept in concepts)


def _default_claims_path(data_dir):
    prepared = data_dir / 'processed/knowledge_claims.jsonl'
    if prepared.exists() or data_dir.resolve() != (ROOT / 'data').resolve():
        return prepared
    return PACKAGED_CLAIMS


def extract_corpus(*, data_dir=ROOT / 'data', existing=None, output=None,
                   report_path=ROOT / 'graph/experiments/claims_corpus_coverage.json',
                   cache_path=ROOT / 'graph/.cache/claims.sqlite3', model=DEFAULT_MODEL,
                   refresh=False, max_new_extractions=None, progress_every=25,
                   selection_path=None):
    """Extract all eligible chunks, validate the merged graph, then publish.

    A deliberate ``max_new_extractions`` stop is useful for time-sliced runs.
    It stores completed chunks in SQLite but never publishes a partial corpus.
    """
    data_dir = Path(data_dir)
    if (selection_path is None and data_dir.resolve() == (ROOT / 'data').resolve()
            and PACKAGED_SELECTION.exists()):
        selection_path = PACKAGED_SELECTION
    existing = Path(existing) if existing is not None else _default_claims_path(data_dir)
    output = Path(output) if output is not None else existing
    report_path = Path(report_path)
    if max_new_extractions is not None and max_new_extractions < 1:
        raise ValueError('max_new_extractions must be positive')
    if progress_every < 1:
        raise ValueError('progress_every must be positive')
    if output.resolve() == report_path.resolve():
        raise ValueError('Claim output and coverage report need different paths')

    inputs, provenance = load_inputs(data_dir)
    taxonomy, chunks = inputs['taxonomy'], inputs['chunks']
    chunk_by_id = {chunk['chunk_id']: chunk for chunk in chunks}
    if len(chunk_by_id) != len(chunks):
        raise ValueError('Duplicate chunk IDs in corpus')
    allowed = catalog(taxonomy)
    eligible_ids = {chunk['chunk_id'] for chunk in chunks if _eligible(chunk, allowed.values())}
    # Existing curated rows take precedence when an extractor produces the
    # same content ID with different model provenance.
    curated = {}
    for row in read_jsonl(existing) if existing.exists() else []:
        validate_claim(row, chunk_by_id, allowed)
        cid = row['claim_id']
        if cid in curated and curated[cid] != row:
            raise ValueError(f'Conflicting existing Claim ID: {cid}')
        curated[cid] = row

    revision = model_revision(model) if eligible_ids else ''
    generated = {}
    coverage = []
    cache_hits = new_extractions = 0
    partial = False
    cache = ClaimCache(cache_path)
    try:
        for index, chunk in enumerate(chunks, 1):
            cid = chunk['chunk_id']
            if cid not in eligible_ids:
                coverage.append({'chunk_id': cid, 'source_id': chunk['source_id'],
                                 'result': 'no_taxonomy_mention', 'generated_claims': 0})
                continue
            found, reused = cache.get_or_extract(chunk, taxonomy, model, revision,
                                                  refresh=refresh)
            cache_hits += int(reused)
            new_extractions += int(not reused)
            for row in found:
                validate_claim(row, chunk_by_id, allowed)
                old = generated.get(row['claim_id'])
                if old is not None and old != row:
                    raise ValueError(f'Conflicting generated Claim ID: {row["claim_id"]}')
                generated[row['claim_id']] = row
            coverage.append({'chunk_id': cid, 'source_id': chunk['source_id'],
                             'result': 'claims' if found else 'processed_no_claim',
                             'generated_claims': len(found), 'cache_hit': reused})
            if index % progress_every == 0 or index == len(chunks):
                print(f'{index}/{len(chunks)} chunks; {new_extractions} new extractions; '
                      f'{cache_hits} cache hits; {len(generated)} generated Claims', flush=True)
            if max_new_extractions is not None and new_extractions >= max_new_extractions \
                    and index < len(chunks):
                partial = True
                break
    finally:
        cache.close()

    if partial:
        print(f'Checkpoint saved in {cache_path}; published Claims unchanged.', flush=True)
        return {'complete': False, 'chunks_visited': len(coverage),
                'chunks_total': len(chunks), 'eligible_total': len(eligible_ids),
                'new_extractions': new_extractions, 'cache_hits': cache_hits}

    raw_generated_count = len(generated)
    excluded_count = corrected_count = 0
    if selection_path is not None:
        selection = json.loads(Path(selection_path).read_text())
        if selection.get('corpus_hash') != digest(chunks):
            raise ValueError('Claim selection belongs to a different source corpus')
        for cid in selection.get('excluded', {}):
            excluded_count += int(generated.pop(cid, None) is not None)
        correctable = {'quote', 'concept_ids', 'subject_id', 'predicate',
                       'object_concept_id', 'object_text', 'polarity', 'qualifier_text'}
        for cid, change in selection.get('corrections', {}).items():
            if cid not in generated:
                continue
            updates = {key: value for key, value in change.items() if key != 'reason'}
            if set(updates) - correctable:
                raise ValueError('Claim correction contains unsupported fields')
            row = {**generated.pop(cid), **updates}
            row['claim_id'] = claim_identifier(row)
            validate_claim(row, chunk_by_id, allowed)
            generated[row['claim_id']] = row
            corrected_count += 1
    # Retain curated wording/provenance on duplicate IDs.
    merged = {**generated, **curated}
    merged_rows = [merged[cid] for cid in sorted(merged)]
    serial = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in merged_rows)
    provenance['claims'] = {'path': str(output),
                            'sha256': hashlib.sha256(serial.encode('utf-8')).hexdigest()}
    _, build_report = build_graph(taxonomy, inputs['users'], inputs['events'], chunks,
                                  provenance=provenance, claims=merged_rows)
    counts = Counter(item['result'] for item in coverage)
    published_by_chunk = Counter(row['chunk_id'] for row in merged_rows)
    source_coverage = {}
    for item in coverage:
        item['published_claims'] = published_by_chunk[item['chunk_id']]
        source = source_coverage.setdefault(item['source_id'], {
            'chunks': 0, 'eligible_chunks': 0, 'generated_proposals': 0,
            'published_claims': 0, 'covered_chunks': 0,
        })
        source['chunks'] += 1
        source['eligible_chunks'] += int(item['chunk_id'] in eligible_ids)
        source['generated_proposals'] += item['generated_claims']
        source['published_claims'] += item['published_claims']
        source['covered_chunks'] += int(item['published_claims'] > 0)
    covered = {row['chunk_id'] for row in merged_rows}
    sources = {chunk_by_id[cid]['source_id'] for cid in covered}
    report = {
        'complete': True, 'model': model, 'model_revision': revision,
        'corpus_hash': digest(chunks), 'chunks_visited': len(coverage),
        'chunks_total': len(chunks), 'sources_total': len({c['source_id'] for c in chunks}),
        'eligible_total': len(eligible_ids), 'no_taxonomy_mention': counts['no_taxonomy_mention'],
        'eligible_with_generated_claims': counts['claims'],
        'eligible_without_generated_claims': counts['processed_no_claim'],
        'eligible_without_published_claims': sum(not published_by_chunk[cid]
                                                for cid in eligible_ids),
        'cache_hits': cache_hits, 'new_extractions': new_extractions,
        'curated_claims_preserved': len(curated),
        'generated_proposals': raw_generated_count, 'generated_claims': len(generated),
        'excluded_proposals': excluded_count, 'corrected_proposals': corrected_count,
        'published_claims': len(merged_rows), 'covered_chunks': len(covered),
        'covered_sources': len(sources), 'snapshot': build_report['snapshot'],
        'claims_sha256': provenance['claims']['sha256'],
        'selection_path': str(selection_path) if selection_path is not None else None,
        'selection_sha256': (hashlib.sha256(Path(selection_path).read_bytes()).hexdigest()
                             if selection_path is not None else None),
        'source_coverage': source_coverage, 'chunks': coverage,
    }
    # Both files are replaced only after the full graph has passed validation.
    _atomic_text(output, serial)
    _atomic_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Published {len(merged_rows)} Claims covering {len(covered)}/{len(chunks)} '
          f'chunks to {output}; coverage report: {report_path}', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--existing', type=Path, help='Curated Claims to retain by ID')
    parser.add_argument('--output', type=Path, help='Published merged JSONL (default: existing)')
    parser.add_argument('--report', type=Path,
                        default=ROOT / 'graph/experiments/claims_corpus_coverage.json')
    parser.add_argument('--cache', type=Path, default=ROOT / 'graph/.cache/claims.sqlite3')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--selection', type=Path,
                        help='Source-bound exclusions/corrections (packaged selection is used for standard data)')
    parser.add_argument('--max-new-extractions', type=int,
                        help='Stop after N uncached calls; checkpoint only, no publication')
    parser.add_argument('--progress-every', type=int, default=25)
    args = parser.parse_args()
    extract_corpus(data_dir=args.data_dir, existing=args.existing, output=args.output,
                   report_path=args.report, cache_path=args.cache, model=args.model,
                   refresh=args.refresh, max_new_extractions=args.max_new_extractions,
                   progress_every=args.progress_every, selection_path=args.selection)


if __name__ == '__main__':
    main()
