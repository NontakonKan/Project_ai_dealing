"""Incremental cache for source-grounded claim extraction."""
import json
import sqlite3
import urllib.request
import os
from pathlib import Path

from . import claims
from .model import digest

CACHE_VERSION = 1


def model_revision(model):
    """Resolve a mutable Ollama tag to its current model digest without inference."""
    url = os.environ.get('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    with urllib.request.urlopen(url + '/api/tags', timeout=15) as response:
        models = json.load(response)['models']
    names = {model, model + ':latest'}
    for entry in models:
        if entry.get('name') in names or entry.get('model') in names:
            if entry.get('digest'):
                return entry['digest']
    raise ValueError(f'Model not found or missing digest: {model}; run ollama pull {model}')


class ClaimCache:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, timeout=30)
        self.con.execute('CREATE TABLE IF NOT EXISTS extractions '
                         '(cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.con.commit()

    def close(self):
        self.con.close()

    def get_or_extract(self, chunk, taxonomy, model, revision, *, refresh=False):
        # Include implementation changes as well as prompt/schema/catalog inputs.
        key = digest({'version': CACHE_VERSION, 'extractor': claims.VERSION,
                      'implementation': digest(Path(claims.__file__).read_text()),
                      'chunk': chunk, 'taxonomy': taxonomy, 'model': model, 'revision': revision})
        stored = None if refresh else self.con.execute(
            'SELECT payload FROM extractions WHERE cache_key=?', (key,)).fetchone()
        if stored:
            try:
                rows = json.loads(stored[0])
                self._validate(rows, chunk, taxonomy)
                return rows, True
            except (ValueError, TypeError, KeyError):
                # Corrupt entries are never used; a failed re-extraction does not cache success.
                pass
        rows = claims.extract(chunk, taxonomy, model)
        self._validate(rows, chunk, taxonomy)
        with self.con:
            self.con.execute('INSERT OR REPLACE INTO extractions VALUES (?,?)',
                             (key, json.dumps(rows, ensure_ascii=False)))
        return rows, False

    @staticmethod
    def _validate(rows, chunk, taxonomy):
        if not isinstance(rows, list) or len(rows) > 3:
            raise ValueError('Invalid cached extraction')
        for row in rows:
            claims.validate_claim(row, {chunk['chunk_id']: chunk}, claims.catalog(taxonomy))
