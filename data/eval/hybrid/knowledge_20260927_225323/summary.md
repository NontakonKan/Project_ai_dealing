| config | Hit@5 | MRR@5 | hit_paraphrase | empty_on_unanswerable | ms_per_query |
|---|---|---|---|---|---|
| dense | 0.852 | 0.741 | 1.0 | 0/3 | 447.3 |
| dense + rerank20 | 0.889 | 0.852 | 1.0 | 0/3 | 1333.1 |
| graph | 0.481 | 0.365 | 0.0 | 3/3 | 92.0 |
| hybrid rrf | 1.0 | 0.841 | 1.0 | 0/3 | 62.5 |
| hybrid rrf + rerank20 | 1.0 | 0.873 | 1.0 | 0/3 | 1146.4 |
| routed | 1.0 | 0.864 | 1.0 | 0/3 | 76.0 |
| routed + rerank20 | 1.0 | 0.895 | 1.0 | 0/3 | 1160.3 |
