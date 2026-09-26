# Dense embedding model comparison (2026-09-26)

The same 292 ground-truth query users and four ChromaDB collections were used for each model. Each index was rebuilt from the same 292 personas, 292 preferences, 231 avoids, and 44 knowledge chunks. Vectors were normalized, and Chroma used cosine distance. E5 received its required `query:`/`passage:` prefixes: preferences and live questions were queries; personas, avoids, and knowledge were passages. All results below use threshold `0.0`, negative penalty `0.15`, and identical eligibility filters and ranking code. No LLM was used.

| Embedding model | Weight file (approx.) | Precision@5 | MRR | nDCG@5 | Violation@5 | Recall@10 |
|---|---:|---:|---:|---:|---:|---:|
| **[BGE-M3](https://huggingface.co/BAAI/bge-m3)** | 2166 MB | **0.1568** | **0.3487** | **0.1688** | **0.0884** | **0.2801** |
| [multilingual-E5-large](https://huggingface.co/intfloat/multilingual-e5-large) | 2136 MB | 0.1507 | 0.3104 | 0.1605 | 0.0911 | 0.2500 |
| [multilingual-E5-base](https://huggingface.co/intfloat/multilingual-e5-base) | 1061 MB | 0.1027 | 0.2041 | 0.1051 | 0.1048 | 0.1753 |
| [multilingual MiniLM L12](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | 449 MB | 0.0836 | 0.1628 | 0.0832 | 0.1233 | 0.1479 |

**Decision:** keep `BAAI/bge-m3` as the default Dense embedding model. It ranked relevant candidates highest in this test and had the lowest excluded-candidate rate at K=5. E5-large was close on Precision@5 but lower on MRR and nDCG. BGE-M3 also supports longer input sequences than E5 and MiniLM, which is useful for book chunks. These are matching-retrieval results on synthetic users, not measured answer quality, Thai knowledge retrieval, or production-user outcomes. Revisit the choice with real consented evaluation data.

To reproduce in a fresh clone, install `requirements-dense.txt`, then run:

```powershell
python -m pipelines.dense.run models
python -m pipelines.dense.run --index data/dense_benchmarks/bge-m3 build --model bge-m3
python -m pipelines.dense.run --index data/dense_benchmarks/e5-large build --model e5-large
python -m pipelines.dense.run --index data/dense_benchmarks/e5-base build --model e5-base
python -m pipelines.dense.run --index data/dense_benchmarks/minilm build --model minilm
python -m pipelines.dense.run --index data/dense_benchmarks/bge-m3 evaluate --top-ks 5 10 20 --thresholds 0.0 --penalty-weights 0.0 0.15
```

Repeat the last command with `e5-large`, `e5-base`, and `minilm`. Comparison indexes are ignored by Git. For ordinary use, `python -m pipelines.dense.run build` selects BGE-M3 in `data/chroma_db/`.
