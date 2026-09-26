"""Thai-capable sentence embeddings with normalized vectors."""
from functools import lru_cache

import numpy as np

DEFAULT_MODEL = "BAAI/bge-m3"
MODEL_ALIASES = {
    "bge-m3": DEFAULT_MODEL,
    "e5-base": "intfloat/multilingual-e5-base",
    "e5-large": "intfloat/multilingual-e5-large",
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}


def resolve_model_name(name):
    return MODEL_ALIASES.get(name, name)


def prepare_texts(texts, model_name, role="document"):
    """Apply a model's retrieval instructions before embedding."""
    if resolve_model_name(model_name).startswith("intfloat/multilingual-e5-"):
        prefix = "query: " if role == "query" else "passage: "
        return [prefix + text for text in texts]
    return texts


@lru_cache(maxsize=2)
def get_model(name=DEFAULT_MODEL):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install Dense dependencies: pip install -r requirements-dense.txt") from exc
    return SentenceTransformer(name)


def encode(texts, model_name=DEFAULT_MODEL, role="document"):
    model_name = resolve_model_name(model_name)
    model = get_model(model_name)
    vectors = model.encode(prepare_texts(texts, model_name, role), batch_size=32,
                           show_progress_bar=len(texts) > 100,
                           normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vectors, dtype=np.float32)
