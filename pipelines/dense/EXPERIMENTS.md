# Dense retrieval experiment (2026-09-26)

This is a real BGE-M3 embedding run on the repository's synthetic data, not the deterministic smoke test. The vectors were generated from 292 consenting personas, 292 preferences, 231 nonempty avoids, and 44 knowledge chunks. The evaluation uses 292 ground-truth query users. Model: `BAAI/bge-m3` through Sentence Transformers 5.7.0, cosine similarity on normalized embeddings. The data was rebuilt into four ChromaDB 1.5.9 collections; the K=5, threshold=0 rows below were reproduced exactly after migration.

Command (after `python -m pipelines.dense.run build`):

```powershell
python -m pipelines.dense.run evaluate --top-ks 5 10 20 --thresholds 0.0 0.55 0.65 --penalty-weights 0.0 0.15 0.3
```

Selected results:

| K | Min directional cosine | Penalty weight | Precision@K | Recall@K | MRR | nDCG@K | Violation@K |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.00 | 0.00 | 0.1582 | 0.1582 | 0.3486 | 0.1703 | 0.0897 |
| 5 | 0.00 | 0.15 | 0.1568 | 0.1568 | 0.3487 | 0.1688 | 0.0884 |
| 5 | 0.65 | 0.00 | 0.0705 | 0.0705 | 0.1593 | 0.0779 | 0.0288 |
| 10 | 0.00 | 0.00 | 0.1366 | 0.2733 | 0.3733 | 0.2332 | 0.1014 |
| 10 | 0.00 | 0.15 | 0.1401 | 0.2801 | 0.3727 | 0.2359 | 0.0952 |
| 20 | 0.00 | 0.00 | 0.1091 | 0.4363 | 0.3840 | 0.3028 | 0.1098 |
| 20 | 0.00 | 0.15 | 0.1086 | 0.4342 | 0.3845 | 0.3018 | 0.1065 |

Increasing K raises recall and lowers precision. The negative-example penalty reduces violations slightly, but does not reliably improve precision. A 0.65 threshold reduces violations partly by returning fewer candidates and sharply reduces recall, so it is not a free improvement. A 0.55 threshold did not affect the selected rows. Dense-only similarity cannot guarantee exclusion of reported red flags; Graph/Hybrid should apply structural constraints. The mock ground truth is derived from synthetic profiles, so these scores do not measure real-world matching quality. LLM answer quality was not measured because no local or hosted LLM endpoint was configured.
