import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph.claims import claim_identifier
from graph.extract_corpus import extract_corpus
from graph.model import digest


class CorpusExtractionTests(unittest.TestCase):
    def setUp(self):
        from graph.tests.test_claims import ClaimTests
        fixture = ClaimTests()
        fixture.setUp()
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.data_dir = root / 'data'
        (self.data_dir / 'mock').mkdir(parents=True)
        (self.data_dir / 'processed').mkdir()
        self.existing = self.data_dir / 'processed/knowledge_claims.jsonl'
        self.report = root / 'coverage.json'
        self.cache = root / 'claims.sqlite3'
        self.chunks = [fixture.chunk,
                       {**fixture.chunk, 'chunk_id': 'c2', 'source_id': 's2',
                        'text': 'banana pineapple orange apple without other labels'},
                       {**fixture.chunk, 'chunk_id': 'c3', 'source_id': 's3'}]
        self.curated = fixture.row
        self.generated_same_id = {**fixture.row, 'model': 'another-model'}
        self.new = {**fixture.row, 'chunk_id': 'c3', 'chunk_hash': digest(self.chunks[2])}
        self.new['claim_id'] = claim_identifier(self.new)
        (self.data_dir / 'taxonomy.json').write_text(json.dumps(fixture.tax, ensure_ascii=False))
        (self.data_dir / 'mock/users.json').write_text('[]')
        (self.data_dir / 'mock/events.jsonl').write_text('')
        (self.data_dir / 'processed/book_chunks.jsonl').write_text(
            ''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in self.chunks))
        self.original = json.dumps(self.curated, ensure_ascii=False) + '\n'
        self.existing.write_text(self.original)

    def tearDown(self):
        self.temp.cleanup()

    def run_corpus(self, **options):
        return extract_corpus(data_dir=self.data_dir, existing=self.existing,
                              report_path=self.report, cache_path=self.cache,
                              progress_every=1, **options)

    def test_checkpoint_resume_and_preserve_curated_claim(self):
        def generated(chunk, taxonomy, model):
            return [self.generated_same_id] if chunk['chunk_id'] == 'c1' else [self.new]

        with patch('graph.extract_corpus.model_revision', return_value='digest1'), \
             patch('graph.claims.extract', side_effect=generated) as extractor:
            partial = self.run_corpus(max_new_extractions=1)
            self.assertFalse(partial['complete'])
            self.assertEqual(self.existing.read_text(), self.original)
            self.assertFalse(self.report.exists())
            complete = self.run_corpus()

        self.assertTrue(complete['complete'])
        self.assertEqual(complete['chunks_total'], 3)
        self.assertEqual(complete['eligible_total'], 2)
        self.assertEqual(complete['no_taxonomy_mention'], 1)
        self.assertEqual(complete['cache_hits'], 1)
        self.assertEqual(complete['new_extractions'], 1)
        self.assertEqual(complete['published_claims'], 2)
        self.assertEqual(complete['covered_chunks'], 2)
        self.assertEqual(extractor.call_count, 2)
        rows = [json.loads(line) for line in self.existing.read_text().splitlines()]
        self.assertEqual({r['claim_id']: r for r in rows}[self.curated['claim_id']], self.curated)
        self.assertEqual(json.loads(self.report.read_text())['published_claims'], 2)

    def test_model_failure_keeps_published_claims(self):
        with patch('graph.extract_corpus.model_revision', return_value='digest1'), \
             patch('graph.claims.extract', side_effect=RuntimeError('model offline')):
            with self.assertRaisesRegex(RuntimeError, 'model offline'):
                self.run_corpus()
        self.assertEqual(self.existing.read_text(), self.original)
        self.assertFalse(self.report.exists())

    def test_source_selection_corrects_generated_rows_and_keeps_existing_claims(self):
        proposed = {**self.new, 'predicate': 'associated_with'}
        proposed['claim_id'] = claim_identifier(proposed)
        selection = Path(self.temp.name) / 'selection.json'
        selection.write_text(json.dumps({
            'corpus_hash': digest(self.chunks),
            'excluded': {self.curated['claim_id']: 'Redundant model extraction'},
            'corrections': {proposed['claim_id']: {
                'predicate': 'decreases', 'reason': 'Source explicitly says reduce'}},
        }))

        def generated(chunk, taxonomy, model):
            return [self.generated_same_id] if chunk['chunk_id'] == 'c1' else [proposed]

        with patch('graph.extract_corpus.model_revision', return_value='digest1'), \
             patch('graph.claims.extract', side_effect=generated):
            report = self.run_corpus(selection_path=selection)
        published = [json.loads(line) for line in self.existing.read_text().splitlines()]
        self.assertEqual({row['claim_id'] for row in published},
                         {self.curated['claim_id'], self.new['claim_id']})
        self.assertEqual(report['excluded_proposals'], 1)
        self.assertEqual(report['corrected_proposals'], 1)


if __name__ == '__main__':
    unittest.main()
