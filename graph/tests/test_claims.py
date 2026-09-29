import unittest
from collections import Counter
from unittest.mock import patch
from types import SimpleNamespace

from graph.build import build_graph
from graph.claims import VERSION, DEFAULT_MODEL, claim_identifier, extract, source_passages
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
                    'concept_ids': ['trait:test'], 'subject_id': 'trait:test',
                    'predicate': 'decreases', 'object_concept_id': '', 'object_text': 'ความขัดแย้ง',
                    'polarity': 'uncertain', 'qualifier_text': 'ในคู่รักบางกลุ่ม',
                    'model': DEFAULT_MODEL, 'extractor_version': VERSION, 'review_status': 'unverified'}
        self.row['claim_id'] = claim_identifier(self.row)

    def build(self, claims):
        return build_graph(self.tax, [], [], [self.chunk], claims=claims)[0]

    def test_stable_graph_and_original_chunk_retrieval(self):
        graph = self.build([self.row])
        self.assertEqual(graph, self.build([self.row, self.row]))
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            result = GraphKnowledge(GraphView(graph)).retrieve('สื่อสาร')
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].id, self.row['claim_id'])
        self.assertEqual(result.items[0].meta['chunk_id'], 'c1')
        self.assertEqual(result.items[0].kind, 'chunk')
        self.assertEqual(result.items[0].text, self.chunk['text'])
        self.assertEqual(result.items[0].meta['claim_ids'], [self.row['claim_id']])
        self.assertEqual(GraphView(graph).rules, {})
        self.assertFalse(any(item.kind == 'graph_fact' for item in result.items))

    def test_reviewed_claim_returns_structured_fact_with_source_path(self):
        reviewed = {**self.row, 'review_status': 'human_verified', 'reviewed_by': 'reviewer-1',
                    'reviewed_at': '2026-09-28T12:00:00+07:00'}
        graph = self.build([reviewed])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            result = GraphKnowledge(GraphView(graph)).retrieve('การสื่อสารอาจลดความขัดแย้งได้')
        fact = next(item for item in result.items if item.kind == 'graph_fact')
        self.assertEqual(fact.id, self.row['claim_id'])
        self.assertEqual(fact.meta['verification_status'], 'human_verified')
        self.assertEqual(fact.meta['evidence_chunk_ids'], ['c1'])
        self.assertEqual(fact.meta['evidence_paths'], [
            ['trait:test', '<-SUBJECT-', self.row['claim_id'],
             'SUPPORTED_BY', 'c1', '<-HAS_CHUNK-', 'source:s1']])
        self.assertEqual(fact.meta['predicate'], 'decreases')
        self.assertIn(self.chunk['text'], fact.text)
        self.assertIn('ในคู่รักบางกลุ่ม', fact.text)

    def test_source_excerpt_keeps_paragraph_conditions_and_exact_offsets(self):
        quote = self.chunk['text']
        paragraph = quote + ' งานนี้ยังไม่ยืนยันความเป็นเหตุเป็นผล'
        chunk = {**self.chunk, 'text': 'หัวข้ออื่นก่อนหน้า\n' + paragraph + '\nหัวข้ออื่นถัดไป'}
        row = {**self.row, 'chunk_hash': digest(chunk)}
        row['claim_id'] = claim_identifier(row)
        graph, _ = build_graph(self.tax, [], [], [chunk], claims=[row])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            item = GraphKnowledge(GraphView(graph)).retrieve('สื่อสาร').items[0]
        self.assertEqual(item.kind, 'chunk')
        self.assertEqual(item.text, paragraph)
        start, end = item.meta['source_text_range']
        self.assertEqual(chunk['text'][start:end], item.text)
        self.assertIn('ยังไม่ยืนยัน', item.text)

    def test_hybrid_keeps_graph_source_excerpt_when_dense_has_the_full_chunk(self):
        from pipelines.hybrid.retrievers import HybridKnowledge
        from unittest.mock import Mock
        chunk = {**self.chunk, 'text': 'หัวข้ออื่นก่อนหน้า\n' + self.chunk['text'] + '\nหัวข้ออื่นถัดไป'}
        row = {**self.row, 'chunk_hash': digest(chunk)}
        row['claim_id'] = claim_identifier(row)
        graph, _ = build_graph(self.tax, [], [], [chunk], claims=[row])
        view = GraphView(graph)
        dense = Mock()
        dense.search.return_value = [{'id': 'c1', 'text': chunk['text'], 'score': 0.7}]
        hybrid = HybridKnowledge(SimpleNamespace(graph=view, dense=dense))
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            items = {it.id: it for it in hybrid.retrieve('สื่อสาร').items}
        self.assertEqual(items['c1'].text, chunk['text'])
        excerpt = items[row['claim_id']]
        self.assertEqual(excerpt.kind, 'chunk')
        self.assertEqual(excerpt.text, self.row['quote'])
        self.assertEqual(view.prop(excerpt.id, 'source_id'), 's1')
        self.assertEqual(excerpt.meta['chunk_id'], 'c1')

    def test_claim_count_does_not_amplify_a_source_chunk_score(self):
        other = {**self.row, 'predicate': 'associated_with'}
        other['claim_id'] = claim_identifier(other)
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            single = GraphKnowledge(GraphView(self.build([self.row]))).retrieve('สื่อสาร').items[0]
            multiple = GraphKnowledge(GraphView(self.build([self.row, other]))).retrieve('สื่อสาร').items[0]
        self.assertEqual(single.score, multiple.score)
        self.assertEqual(multiple.meta['chunk_id'], 'c1')
        self.assertEqual(len(multiple.meta['claim_ids']), 2)

    def test_other_aspects_of_a_concept_keep_the_lexical_fallback(self):
        other = {'chunk_id': 'c2', 'source_id': 's2', 'pages': [2], 'concepts': [],
                 'text': 'banana pineapple banana orange'}
        graph, _ = build_graph(self.tax, [], [], [self.chunk, other], claims=[self.row])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            items = GraphKnowledge(GraphView(graph)).retrieve('banana').items
        self.assertTrue(any(it.id == 'c2' for it in items))

    def test_large_graph_pool_does_not_double_unrelated_dense_votes(self):
        other = {'chunk_id': 'c2', 'source_id': 's2', 'pages': [2], 'concepts': [],
                 'text': 'ความขัดแย้ง banana pineapple banana orange'}
        graph, _ = build_graph(self.tax, [], [], [self.chunk, other], claims=[self.row])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            items = GraphKnowledge(GraphView(graph)).retrieve('ความขัดแย้ง', 40).items
        self.assertFalse(any(it.id == 'c2' for it in items))
        self.assertTrue(any(it.meta['chunk_id'] == 'c1' for it in items))

    def test_later_claim_recovers_its_source_introduction(self):
        chunk = {**self.chunk, 'chunk_id': 'book_s00_c02'}
        intro = {**chunk, 'chunk_id': 'book_s00_c00', 'text': 'นิยามและบริบทของการศึกษาฉบับนี้'}
        middle = {**chunk, 'chunk_id': 'book_s00_c01', 'text': 'รายละเอียดขั้นตอนการศึกษาต่อเนื่อง'}
        row = {**self.row, 'chunk_id': chunk['chunk_id'], 'chunk_hash': digest(chunk)}
        row['claim_id'] = claim_identifier(row)
        graph, _ = build_graph(self.tax, [], [], [intro, middle, chunk], claims=[row])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            items = GraphKnowledge(GraphView(graph)).retrieve('ความขัดแย้ง').items
        item = next(it for it in items if it.id == intro['chunk_id'])
        self.assertEqual(item.text, intro['text'])
        self.assertEqual(item.meta['source_context_for'], [chunk['chunk_id']])
        self.assertEqual(item.meta['claim_ids'], [])

    def test_prediction_question_does_not_promote_a_different_claim(self):
        reviewed = {**self.row, 'review_status': 'human_verified', 'reviewed_by': 'reviewer-1',
                    'reviewed_at': '2026-09-28T12:00:00+07:00'}
        graph = self.build([reviewed])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            result = GraphKnowledge(GraphView(graph)).retrieve('การสื่อสารทำนายความขัดแย้งไหม')
        self.assertFalse(any(item.kind == 'graph_fact' for item in result.items))
        self.assertTrue(all(not item.meta['claim_ids'] for item in result.items))

    def test_strong_predicate_must_target_the_outcome_beside_its_cue(self):
        chunk = {**self.chunk, 'text': 'การสื่อสารทำนายการผูกมัดในความสัมพันธ์ แต่ความขัดแย้งเป็นอีกตัวแปรหนึ่ง'}
        row = {**self.row, 'chunk_hash': digest(chunk), 'quote': chunk['text'],
               'predicate': 'predicts', 'object_text': 'ความขัดแย้ง',
               'qualifier_text': '', 'polarity': 'affirmed'}
        row['claim_id'] = claim_identifier(row)
        with self.assertRaisesRegex(ValueError, 'Strong claim predicate'):
            build_graph(self.tax, [], [], [chunk], claims=[row])
        row['object_text'] = 'การผูกมัด'
        row['claim_id'] = claim_identifier(row)
        build_graph(self.tax, [], [], [chunk], claims=[row])

    def test_two_hop_retrieval_returns_both_reviewed_source_claims(self):
        self.tax['traits'] = [
            {'id': 'trait:a', 'label_th': 'การสื่อสาร'},
            {'id': 'trait:b', 'label_th': 'ความขัดแย้ง'},
            {'id': 'trait:c', 'label_th': 'ความพึงพอใจ'},
        ]
        chunks = [
            {'chunk_id': 'c-a-b', 'source_id': 's1', 'pages': [1], 'concepts': [],
             'text': 'การสื่อสารสัมพันธ์กับความขัดแย้งในตัวอย่างนี้'},
            {'chunk_id': 'c-b-c', 'source_id': 's2', 'pages': [2], 'concepts': [],
             'text': 'ความขัดแย้งลดความพึงพอใจในกลุ่มดังกล่าว'},
        ]

        def reviewed(chunk, subject, predicate, object_id, object_text, concepts):
            row = {'chunk_id': chunk['chunk_id'], 'chunk_hash': digest(chunk), 'quote': chunk['text'],
                   'concept_ids': concepts, 'subject_id': subject, 'predicate': predicate,
                   'object_concept_id': object_id, 'object_text': object_text,
                   'polarity': 'affirmed', 'qualifier_text': '', 'model': DEFAULT_MODEL,
                   'extractor_version': VERSION, 'review_status': 'human_verified',
                   'reviewed_by': 'reviewer-1', 'reviewed_at': '2026-09-28T12:00:00+07:00'}
            row['claim_id'] = claim_identifier(row)
            return row

        claims = [
            reviewed(chunks[0], 'trait:a', 'associated_with', 'trait:b', 'ความขัดแย้ง',
                     ['trait:a', 'trait:b']),
            reviewed(chunks[1], 'trait:b', 'decreases', 'trait:c', 'ความพึงพอใจ',
                     ['trait:b', 'trait:c']),
        ]
        graph, _ = build_graph(self.tax, [], [], chunks, claims=claims)
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:a', 'trait:c'}):
            result = GraphKnowledge(GraphView(graph)).retrieve('การสื่อสารสัมพันธ์กับความพึงพอใจ')
        facts = [item for item in result.items if item.kind == 'graph_fact']
        self.assertEqual({item.id for item in facts}, {c['claim_id'] for c in claims})
        self.assertTrue(all(item.meta['claim_ids'] == [c['claim_id'] for c in claims] for item in facts))
        self.assertTrue(all(len(item.meta['path']) == 2 for item in facts))

    def test_unverified_taxonomy_rule_is_not_returned_as_evidence(self):
        self.tax['compatibility_rules'] = [{'a': 'trait:test', 'b': 'trait:test',
            'relation': 'COMPATIBLE_WITH', 'weight': 0.8, 'reason': 'assumption'}]
        graph = self.build([])
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:test'}):
            result = GraphKnowledge(GraphView(graph)).retrieve('สื่อสาร')
        self.assertFalse(any(item.id.startswith('rule:') for item in result.items))
        self.assertFalse(any(item.kind == 'graph_fact' for item in result.items))

    def test_lexical_entry_preserves_source_path_and_diversity(self):
        chunks = [
            {'chunk_id': f'a{i}', 'source_id': 'source-a', 'title': 'การสื่อสาร',
             'pages': [i], 'concepts': [], 'text': 'การสื่อสารและการตั้งขอบเขตในความสัมพันธ์'}
            for i in range(3)
        ] + [{'chunk_id': 'b0', 'source_id': 'source-b', 'title': 'ความสัมพันธ์',
              'pages': [4], 'concepts': [], 'text': 'การตั้งขอบเขตช่วยให้คู่รักเข้าใจกัน'}]
        graph, _ = build_graph(self.tax, [], [], chunks)
        with patch('graph.retrieve.concept_detector.detect', return_value=set()):
            items = GraphKnowledge(GraphView(graph), use_embedding=False).retrieve('การตั้งขอบเขต', 3).items
        self.assertEqual(len(items), 3)
        self.assertEqual(Counter(item.meta['source_id'] for item in items),
                         {'source-a': 2, 'source-b': 1})
        self.assertTrue(all(item.meta['path'] ==
                            ['source:' + item.meta['source_id'], 'HAS_CHUNK', item.id]
                            for item in items))

    def test_adjacent_chunk_is_recovered_from_document_order_edge(self):
        chunks = [
            {'chunk_id': 'book_s00_c00', 'source_id': 'book', 'pages': [1], 'concepts': [],
             'text': 'การตั้งขอบเขตในความสัมพันธ์เริ่มจากการบอกความต้องการ'},
            {'chunk_id': 'book_s00_c01', 'source_id': 'book', 'pages': [2], 'concepts': [],
             'text': 'ตัวอย่างการตอบคือปฏิเสธอย่างสุภาพและชัดเจน'},
        ]
        graph, _ = build_graph(self.tax, [], [], chunks)
        with patch('graph.retrieve.concept_detector.detect', return_value=set()):
            items = GraphKnowledge(GraphView(graph), use_embedding=False).retrieve('การตั้งขอบเขต', 2).items
        neighbor = next(item for item in items if item.id == 'book_s00_c01')
        self.assertEqual(neighbor.meta['adjacent_to'], 'book_s00_c00')

    def test_description_linking_requires_clear_concept_match(self):
        from graph.concepts import detect
        self.assertEqual(detect('คนรักทำให้เราสงสัยความจำตัวเองเรียกว่าอะไร', False),
                         {'rf:gaslighting'})
        self.assertEqual(detect('ราคาทองวันนี้เท่าไร', False), set())

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
        proposal = {'passage_id': 'p0', 'concept_ids': ['trait:test'], 'subject_id': 'trait:test',
                    'predicate': 'decreases', 'object_concept_id': '', 'object_text': 'ความขัดแย้ง',
                    'polarity': 'uncertain', 'qualifier_text': 'ในคู่รักบางกลุ่ม'}
        result = SimpleNamespace(text=json.dumps({'claims': [proposal]}), model=DEFAULT_MODEL, metrics={})
        with patch('graph.claims._chat', return_value=result) as model:
            self.assertEqual(extract(self.chunk, self.tax), [self.row])
            self.assertEqual(model.call_args.args[0], 'qwen3.5:9b')
            self.assertEqual(model.call_args.args[2]['type'], 'object')
            claim_fields = model.call_args.args[2]['properties']['claims']['items']['properties']
            self.assertIn('subject_id', claim_fields)
            self.assertIn('predicate', claim_fields)
            result.text = '```json\n' + result.text + '\n```'
            self.assertEqual(extract(self.chunk, self.tax), [self.row])
            result.metrics = {'truncated': True}
            with self.assertRaises(ValueError):
                extract(self.chunk, self.tax)

    def test_long_ocr_line_remains_extractable_with_exact_passages(self):
        line = 'ก' * 900 + 'การสื่อสารช่วยลดความขัดแย้งในคู่รัก' + 'ข' * 600
        passages = source_passages(line)
        self.assertGreaterEqual(len(passages), 2)
        self.assertTrue(all(20 <= len(p) <= 600 and p in line for p in passages.values()))
        self.assertTrue(any('การสื่อสารช่วยลดความขัดแย้ง' in p for p in passages.values()))
        self.assertEqual(passages, source_passages(line))

    def test_invalid_model_proposal_does_not_discard_valid_claim(self):
        import json
        valid = {'passage_id': 'p0', 'concept_ids': ['trait:test'], 'subject_id': 'trait:test',
                 'predicate': 'decreases', 'object_concept_id': '', 'object_text': 'ความขัดแย้ง',
                 'polarity': 'uncertain', 'qualifier_text': 'ในคู่รักบางกลุ่ม'}
        invalid = {**valid, 'object_text': 'ข้อความที่ไม่ได้อยู่ในต้นฉบับ'}
        response = SimpleNamespace(text=json.dumps({'claims': [invalid, valid]}),
                                   model=DEFAULT_MODEL, metrics={})
        with patch('graph.claims._chat', return_value=response), self.assertWarnsRegex(
                UserWarning, 'skipped invalid claim proposal'):
            self.assertEqual(extract(self.chunk, self.tax), [self.row])

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
        row['claim_id'] = claim_identifier(row)
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
            {'passage_id': 'p0', 'concept_ids': ['trait:calm'], 'subject_id': 'trait:calm',
             'predicate': 'associated_with', 'object_concept_id': '', 'object_text': 'การสื่อสาร',
             'polarity': 'affirmed', 'qualifier_text': ''}]}), model=DEFAULT_MODEL, metrics={})
        with patch('graph.claims._chat', return_value=response), self.assertWarns(UserWarning):
            self.assertEqual(extract(chunk, self.tax), [])

    def test_claim_roles_and_review_status_are_validated(self):
        for field, value in [('subject_id', 'unknown'), ('object_text', 'not in quote'),
                             ('predicate', 'invented'), ('polarity', 'maybe'),
                             ('qualifier_text', 'not in quote')]:
            row = {**self.row, field: value}
            row['claim_id'] = claim_identifier(row)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.build([row])
        with self.assertRaisesRegex(ValueError, 'reviewer and timestamp'):
            self.build([{**self.row, 'review_status': 'human_verified'}])

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

    def test_claim_inspection_query_uses_declared_object_variable(self):
        from graph.queries import QUERIES
        query = QUERIES['claims']
        self.assertIn('OPTIONAL MATCH (c)-[:OBJECT]->(obj:Concept)', query)
        self.assertIn('WITH c, b, subject, obj, collect(DISTINCT t.id) AS concepts', query)
        self.assertIn('obj.id AS object_concept_id', query)
