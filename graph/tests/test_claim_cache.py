import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graph.claim_cache import ClaimCache
from graph.tests import test_claims


class CacheTests(unittest.TestCase):
    def setUp(self):
        fixture = test_claims.ClaimTests()
        fixture.setUp()
        self.chunk, self.tax, self.row = fixture.chunk, fixture.tax, fixture.row
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'cache.sqlite3'
        self.cache = ClaimCache(self.path)

    def tearDown(self):
        self.cache.close()
        self.temp.cleanup()

    def get(self, **kwargs):
        args = dict(chunk=self.chunk, taxonomy=self.tax, model='qwen3.5:9b', revision='digest1')
        args.update(kwargs)
        return self.cache.get_or_extract(**args)

    def test_reuse_persists_across_restarts(self):
        with patch('graph.claims.extract', return_value=[self.row]) as extract:
            self.assertFalse(self.get()[1])
            self.cache.close()
            self.cache = ClaimCache(self.path)
            self.assertEqual(self.get(), ([self.row], True))
            extract.assert_called_once()

    def test_empty_result_is_cached(self):
        with patch('graph.claims.extract', return_value=[]) as extract:
            self.get()
            self.assertEqual(self.get(), ([], True))
            extract.assert_called_once()

    def test_invalidation_and_refresh(self):
        with patch('graph.claims.extract', return_value=[]) as extract:
            self.get()
            self.assertFalse(self.get(chunk={**self.chunk, 'text': 'changed'})[1])
            self.assertFalse(self.get(taxonomy={**self.tax, 'extra': 'changed'})[1])
            self.assertFalse(self.get(model='different-model')[1])
            self.assertFalse(self.get(revision='digest2')[1])
            self.assertFalse(self.get(refresh=True)[1])
            self.assertEqual(extract.call_count, 6)

    def test_failure_is_retried_and_invalid_output_not_cached(self):
        with patch('graph.claims.extract', side_effect=[RuntimeError('offline'), [{'bad': True}], []]) as extract:
            with self.assertRaises(RuntimeError): self.get()
            with self.assertRaises(ValueError): self.get()
            self.assertEqual(self.get(), ([], False))
            self.assertEqual(extract.call_count, 3)

    def test_corruption_is_reextracted(self):
        with patch('graph.claims.extract', return_value=[]) as extract:
            self.get()
            with self.cache.con:
                self.cache.con.execute("UPDATE extractions SET payload='not json'")
            self.assertFalse(self.get()[1])
            self.assertEqual(extract.call_count, 2)
