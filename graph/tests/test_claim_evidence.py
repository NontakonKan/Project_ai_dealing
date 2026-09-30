import copy
import json
import unittest
from unittest.mock import patch

from graph.build import build_graph
from graph.claims import VERSION, catalog, claim_identifier, mentioned, validate_claim
from graph.model import content_hash, digest, validate
from graph.retrieve import GraphKnowledge
from graph.schema import GROUP_LABELS
from graph.view import GraphView


class ClaimEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.taxonomy = {group: [] for group in GROUP_LABELS}
        self.taxonomy.update(
            compatibility_rules=[],
            traits=[{'id': 'trait:communication', 'label_th': 'การสื่อสาร'}],
        )
        self.chunk = {
            'chunk_id': 'source_s00_c00', 'source_id': 'source',
            'pages': [1], 'concepts': [],
            'text': 'ในคู่รักบางกลุ่ม การสื่อสารอาจช่วยลดความขัดแย้งได้ แต่ไม่เสมอไป',
        }
        self.row = {
            'chunk_id': self.chunk['chunk_id'], 'chunk_hash': digest(self.chunk),
            'quote': self.chunk['text'], 'concept_ids': ['trait:communication'],
            'subject_id': 'trait:communication', 'predicate': 'decreases',
            'object_concept_id': '', 'object_text': 'ความขัดแย้ง',
            'polarity': 'uncertain', 'qualifier_text': 'ในคู่รักบางกลุ่ม',
            'model': 'extractor-model', 'extractor_version': VERSION,
        }
        self.row['claim_id'] = claim_identifier(self.row)

    def build(self, row=None):
        return build_graph(self.taxonomy, [], [], [self.chunk],
                           claims=[self.row if row is None else row])[0]

    @staticmethod
    def claim_properties(graph):
        return next(node['properties'] for node in graph['nodes'] if node['label'] == 'Claim')

    def test_source_valid_claim_imports_without_status(self):
        row = json.loads(json.dumps(self.row, ensure_ascii=False))
        self.assertEqual(validate_claim(row, {self.chunk['chunk_id']: self.chunk},
                                        catalog(self.taxonomy)), self.row)
        graph = self.build(row)
        props = self.claim_properties(graph)
        self.assertEqual(props['text'], self.chunk['text'])
        self.assertNotIn('assertion', props)
        self.assertFalse(any(key.startswith('review') for key in props))
        self.assertEqual(validate(json.loads(json.dumps(graph)))['nodes_by_label']['Claim'], 1)

    def test_claim_identity_depends_on_evidence_and_roles(self):
        self.assertEqual(claim_identifier(self.row), self.row['claim_id'])
        changed = {**self.row, 'polarity': 'negated'}
        self.assertNotEqual(claim_identifier(changed), self.row['claim_id'])

    def test_retrieval_returns_original_source_without_generated_fact(self):
        retriever = GraphKnowledge(GraphView(self.build()), use_embedding=False)
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:communication'}):
            result = retriever.retrieve('การสื่อสารอาจลดความขัดแย้งได้ไหม')
        self.assertIn(self.row['claim_id'], retriever.claims)
        item = next(item for item in result.items if self.row['claim_id'] in item.meta['claim_ids'])
        self.assertEqual(item.kind, 'chunk')
        self.assertEqual(item.text, self.chunk['text'])
        self.assertEqual(item.meta['chunk_id'], self.chunk['chunk_id'])
        self.assertNotIn('claim_statuses', item.meta)
        self.assertFalse(any(item.kind == 'graph_fact' for item in result.items))

    def test_extra_claim_metadata_is_rejected_before_and_after_build(self):
        graph = self.build()
        for field in ('review_status', 'reviewed_at', 'review_method', 'review_notes',
                      'reviewed_by', 'reviewer_type', 'assertion', 'unknown'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, 'unsupported metadata'):
                    self.build({**self.row, field: 'value'})
                modified = copy.deepcopy(graph)
                self.claim_properties(modified)[field] = 'value'
                modified['snapshot'] = content_hash(modified)
                with self.assertRaisesRegex(ValueError, 'unsupported metadata'):
                    validate(modified)

    def test_source_evidence_cannot_be_removed_after_build(self):
        graph = self.build()
        relation = next(e for e in graph['relationships'] if e['type'] == 'SUPPORTED_BY')
        relation['properties']['evidence'] = 'different quote'
        graph['snapshot'] = content_hash(graph)
        with self.assertRaisesRegex(ValueError, 'exact source evidence'):
            validate(graph)

    def test_stale_source_is_rejected(self):
        self.chunk['text'] += ' ข้อจำกัดของการศึกษา'
        with self.assertRaisesRegex(ValueError, 'stale claim source'):
            self.build()

    def test_love_component_literal_aliases_link_original_theory_terms(self):
        self.taxonomy['love_components'] = [
            {'id': 'love:intimacy', 'label_th': 'ความใกล้ชิด'},
            {'id': 'love:passion', 'label_th': 'ความหลงใหล'},
            {'id': 'love:commitment', 'label_th': 'การผูกมัด'},
        ]
        allowed = catalog(self.taxonomy)
        for cid, phrase in [('love:intimacy', 'Intimacy'), ('love:intimacy', 'Intimate'),
                            ('love:passion', 'Passion'), ('love:passion', 'ความเสน่หา'),
                            ('love:commitment', 'Commitment')]:
            with self.subTest(cid=cid, phrase=phrase):
                self.assertTrue(mentioned(phrase + ' เป็นองค์ประกอบหนึ่งของความรัก', allowed[cid]))
        self.assertFalse(mentioned('Impassioned speech', allowed['love:passion']))

    def test_claim_chain_only_nominates_source_passages(self):
        taxonomy = {group: [] for group in GROUP_LABELS}
        taxonomy.update(compatibility_rules=[], traits=[
            {'id': 'trait:a', 'label_th': 'การสื่อสาร'},
            {'id': 'trait:b', 'label_th': 'ความขัดแย้ง'},
            {'id': 'trait:c', 'label_th': 'ความพึงพอใจ'},
        ])
        chunks = [
            {**self.chunk, 'chunk_id': 'a-b', 'source_id': 's1',
             'text': 'การสื่อสารสัมพันธ์กับความขัดแย้งในกลุ่มตัวอย่างนี้'},
            {**self.chunk, 'chunk_id': 'b-c', 'source_id': 's2',
             'text': 'ความขัดแย้งลดความพึงพอใจในกลุ่มตัวอย่างนี้'},
        ]
        rows = []
        for chunk, subject, predicate, object_id, object_text in [
            (chunks[0], 'trait:a', 'associated_with', 'trait:b', 'ความขัดแย้ง'),
            (chunks[1], 'trait:b', 'decreases', 'trait:c', 'ความพึงพอใจ'),
        ]:
            row = {**self.row, 'chunk_id': chunk['chunk_id'], 'chunk_hash': digest(chunk),
                   'quote': chunk['text'], 'subject_id': subject, 'predicate': predicate,
                   'concept_ids': [subject, object_id], 'object_concept_id': object_id,
                   'object_text': object_text, 'polarity': 'affirmed',
                   'qualifier_text': 'ในกลุ่มตัวอย่างนี้'}
            row['claim_id'] = claim_identifier(row)
            rows.append(row)
        graph, _ = build_graph(taxonomy, [], [], chunks, claims=rows)
        retriever = GraphKnowledge(GraphView(graph), use_embedding=False)
        with patch('graph.retrieve.concept_detector.detect', return_value={'trait:a', 'trait:c'}):
            result = retriever.retrieve('การสื่อสารสัมพันธ์กับความพึงพอใจไหม')
        self.assertEqual(len(retriever.claims), 2)
        self.assertFalse(any(item.kind == 'graph_fact' for item in result.items))
        self.assertEqual({item.meta['chunk_id'] for item in result.items
                          if item.meta['two_hop_paths']}, {'a-b', 'b-c'})


if __name__ == '__main__':
    unittest.main()
