| config | Hit@5 | MRR@5 | hit_paraphrase | empty_on_unanswerable | ms_per_query |
|---|---|---|---|---|---|
| dense | 0.852 | 0.759 | 1.0 | 0/3 | 478.9 |
| dense + rerank20 | 0.889 | 0.852 | 1.0 | 0/3 | 1299.8 |
| graph | 0.481 | 0.365 | 0.0 | 3/3 | 49.1 |
| hybrid rrf | 1.0 | 0.853 | 1.0 | 0/3 | 52.3 |
| hybrid rrf + rerank20 | 1.0 | 0.873 | 1.0 | 0/3 | 1095.8 |
| routed | 1.0 | 0.895 | 1.0 | 0/3 | 67.1 |
| routed + rerank20 | 1.0 | 0.914 | 1.0 | 0/3 | 1115.8 |
