"""Thai-capable sentence embeddings with normalized vectors."""
from functools import lru_cache

import numpy as np

DEFAULT_MODEL = "BAAI/bge-m3"


@lru_cache(maxsize=2)
def get_model(name=DEFAULT_MODEL):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install Dense dependencies: pip install -r requirements-dense.txt") from exc
    return SentenceTransformer(name)


def encode(texts, model_name=DEFAULT_MODEL):
    model = get_model(model_name)
    vectors = model.encode(texts, batch_size=32, show_progress_bar=len(texts) > 100,
                           normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vectors, dtype=np.float32)
