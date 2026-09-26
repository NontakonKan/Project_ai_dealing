# Dense RAG

This module implements the Dense part of the project rubric: BGE-M3 embedding, persistent ChromaDB vector retrieval, context selection, an optional LLM answer, and a retrieval experiment grid.

```powershell
python -m pip install -r requirements-dense.txt
python -m pipelines.dense.run build
python -m pipelines.dense.run models
python -m pipelines.dense.run match U001 --top-k 5 --threshold 0.2
python -m pipelines.dense.run knowledge "การสื่อสารเมื่อเกิดความขัดแย้ง" --top-k 5
python -m pipelines.dense.run knowledge "การสื่อสารเมื่อเกิดความขัดแย้ง" --llm
python -m pipelines.dense.run evaluate
python -m unittest discover -s tests -v
```

The default multilingual embedding model is `BAAI/bge-m3`; this is separate from the team's chat/extraction LLMs. Run `models` to see the compared choices. To select one, pass `build --model bge-m3|e5-base|e5-large|minilm` or a full Sentence Transformers model ID. Use a separate `--index` directory for each model; a Chroma collection must never mix vectors from different embedding models. For example:

```powershell
python -m pipelines.dense.run --index data/dense_benchmarks/e5-base build --model e5-base
python -m pipelines.dense.run --index data/dense_benchmarks/e5-base evaluate --top-ks 5 10 20 --thresholds 0.0 --penalty-weights 0.0 0.15
```

The first build downloads model weights. E5 uses its required `query:` and `passage:` prefixes: preferences and live search text are queries; personas, avoids, and knowledge chunks are passages. Other models use the original text. The generated `data/chroma_db/` stores four persistent ChromaDB collections (`persona_vec`, `preference_vec`, `avoid_vec`, `knowledge_vec`) with vectors, documents, and metadata. Rebuild after changing source data or model. The previous `data/dense_index/` NumPy files are no longer read by the CLI. See [MODEL_COMPARISON.md](MODEL_COMPARISON.md) for model selection and [EXPERIMENTS.md](EXPERIMENTS.md) for BGE-M3 settings.

Matching retrieves candidate personas through ChromaDB, then uses reciprocal preference/persona cosine similarities and their harmonic mean. Hard filters require mutual gender preference, both users' consent, and no prior `unmatch` or `pass` between the pair. A negative example penalty uses the maximum persona similarity to people the querying user previously unmatched. `--threshold` applies to both directional similarities. `knowledge` uses ChromaDB metadata filters for `--category` and `--concept`.

To request an answer from an OpenAI-compatible local or hosted endpoint, set `DENSE_LLM_ENDPOINT`, `DENSE_LLM_MODEL`, and, if needed, `DENSE_LLM_API_KEY`, then use `match U001 --llm` or `knowledge QUESTION --llm`. The endpoint can point to an Ollama OpenAI-compatible server or a hosted provider. Matching sends selected persona summaries and book excerpts to that endpoint; use a local endpoint if the data must remain local.

`evaluate` reads ground truth only in `evaluation.py` and reports Precision@K, Recall@K, MRR, nDCG@K, and Violation@K across Top-K, threshold, and negative penalty settings. Save the JSON report with `python -m pipelines.dense.run evaluate > dense-evaluation.json`. The smoke test checks pipeline wiring with deterministic fake vectors; its scores are not model results. These are retrieval measurements; an LLM answer quality study and comparison with Graph/Hybrid are separate experiments. Mock data is synthetic, so these metrics do not establish real-world matching quality.
