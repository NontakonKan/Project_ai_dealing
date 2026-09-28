import unittest
from unittest.mock import patch
from types import SimpleNamespace

from graph.build import build_graph
from graph.claims import VERSION, DEFAULT_MODEL, extract
from graph.model import digest, validate, content_hash
from graph.schema import GROUP_LABELS
from graph.view import GraphView
from graph.retrieve import GraphKnowledge


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.tax = {g: [] for g in GROUP_LABELS}
        self.tax.update(compatibility_rules=[], traits=[{'id': 'trait:test', 'label_th': 'สื่อสาร'}])
        self.chunk = {'chunk_id': 'c1', 'source_id': 's1', 'pages': [1], 'concepts': [],
                      'text': 'ในคู่รักบางกลุ่ม การสื่อสารอาจช่วยลดความขัดแย้งได้ แต่ไม่เสมอไป'}
        self.row = {'chunk_id': 'c1', 'chunk_hash': digest(self.chunk), 'quote': self.chunk['text'],
                    'concept_ids': ['trait:test'], 'model': DEFAULT_MODEL, 'extractor_version': VERSION}
        self.row['claim_id'] = 'claim:' + digest(['c1', digest(self.chunk), self.row['quote'], ['trait:test']])[:24]

    def build(self, claims):
        return build_graph(self.tax, [], [], [self.chunk], claims=claims)[0]

    def test_stable_graph_and_original_chunk_retrieval(self):
        graph = self.build([self.row])
        self.assertEqual(graph, self.build([self.row, self.row]))
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            result = GraphKnowledge(GraphView(graph)).retrieve('สื่อสาร')
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].id, 'c1')
        self.assertEqual(result.items[0].kind, 'chunk')
        self.assertEqual(result.items[0].text, self.chunk['text'])
        self.assertEqual(result.items[0].meta['claim_ids'], [self.row['claim_id']])
        self.assertEqual(GraphView(graph).rules, {})

    def test_bad_evidence_unknown_concept_and_stale_source_rejected(self):
        for field, value in [('quote', 'ข้อความที่ไม่ได้อยู่ในเอกสารต้นฉบับ'),
                             ('concept_ids', ['unknown']), ('chunk_hash', 'old')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.build([{**self.row, field: value}])

    def test_import_validator_rejects_forged_claim(self):
        graph = self.build([self.row])
        for n in graph['nodes']:
            if n['label'] == 'Claim':
                n['properties']['text'] = 'forged'
        graph['snapshot'] = content_hash(graph)
        with self.assertRaises(ValueError):
            validate(graph)

    def test_model_schema_and_truncation(self):
        import json
        result = SimpleNamespace(text=json.dumps({'claims': [{'passage_id': 'p0',
                                        'concept_ids': ['trait:test']}]}), model=DEFAULT_MODEL, metrics={})
        with patch('graph.claims._chat', return_value=result) as model:
            self.assertEqual(extract(self.chunk, self.tax), [self.row])
            self.assertEqual(model.call_args.args[0], 'qwen3.5:9b')
            self.assertEqual(model.call_args.args[2]['type'], 'object')
            result.text = '```json\n' + result.text + '\n```'
            self.assertEqual(extract(self.chunk, self.tax), [self.row])
            result.metrics = {'truncated': True}
            with self.assertRaises(ValueError):
                extract(self.chunk, self.tax)

    def test_no_claims_preserves_original_graph(self):
        self.assertFalse(any(n['label'] == 'Claim' for n in self.build([])['nodes']))

    def test_graph_request_disables_thinking(self):
        import io
        import json
        from graph.claims import _chat
        with patch('graph.claims.urllib.request.urlopen',
                   return_value=io.BytesIO(b'{"message":{"content":"{}"},"done_reason":"stop"}')) as post:
            result = _chat(DEFAULT_MODEL, [], {'type': 'object'})
            payload = json.loads(post.call_args.args[0].data)
            self.assertIs(payload['think'], False)
            self.assertEqual(payload['model'], DEFAULT_MODEL)
            self.assertEqual(result.text, '{}')

    def test_existing_but_unrelated_concept_is_rejected(self):
        self.tax['traits'].append({'id': 'trait:calm', 'label_th': 'ใจเย็น'})
        row = {**self.row, 'concept_ids': ['trait:calm']}
        row['claim_id'] = 'claim:' + digest(['c1', row['chunk_hash'], row['quote'], row['concept_ids']])[:24]
        with self.assertRaisesRegex(ValueError, 'no label or alias'):
            self.build([row])

    def test_no_matching_concept_skips_model(self):
        chunk = {**self.chunk, 'text': 'บทความนี้กล่าวถึงข้อมูลทั่วไปที่ไม่เกี่ยวกับหัวข้อในรายการ'}
        with patch('graph.claims._chat') as model:
            self.assertEqual(extract(chunk, self.tax), [])
            model.assert_not_called()

    def test_english_alias_word_boundaries(self):
        from graph.claims import mentioned
        concept = {'label': 'secure', 'aliases': []}
        self.assertFalse(mentioned('insecure attachment', concept))
        self.assertTrue(mentioned('Secure attachment', concept))

    def test_secure_attachment_does_not_match_emotional_stability(self):
        from graph.claims import catalog, mentioned
        self.tax['attachment_styles'] = [{'id': 'attach:secure', 'label_th': 'มั่นคง'}]
        concept = catalog(self.tax)['attach:secure']
        self.assertFalse(mentioned('ความมั่นคงทางอารมณ์', concept))
        self.assertTrue(mentioned('ความผูกพันแบบมั่นคง', concept))

    def test_invalid_passage_links_are_dropped_with_warning(self):
        import json
        self.tax['traits'].append({'id': 'trait:calm', 'label_th': 'ใจเย็น'})
        chunk = {**self.chunk, 'text': self.chunk['text'] + '\nคนที่ใจเย็นอาจใช้เวลาคิดก่อนตอบคำถาม'}
        response = SimpleNamespace(text=json.dumps({'claims': [
            {'passage_id': 'p0', 'concept_ids': ['trait:calm']}]}), model=DEFAULT_MODEL, metrics={})
        with patch('graph.claims._chat', return_value=response), self.assertWarns(UserWarning):
            self.assertEqual(extract(chunk, self.tax), [])

    def test_trial_import_does_not_publish_active_pointer(self):
        from unittest.mock import MagicMock
        from graph.neo4j_store import _write_snapshot
        graph = self.build([self.row])
        counts = {'nodes': len(graph['nodes']), 'relationships': len(graph['relationships'])}
        tx = MagicMock()
        with patch('graph.neo4j_store._counts', return_value=counts):
            _write_snapshot(tx, graph, activate=False)
        self.assertFalse(any('SET d.active_snapshot' in call.args[0] for call in tx.run.call_args_list))
        tx.reset_mock()
        with patch('graph.neo4j_store._counts', return_value=counts):
            _write_snapshot(tx, graph)
        self.assertTrue(any('SET d.active_snapshot' in call.args[0] for call in tx.run.call_args_list))
