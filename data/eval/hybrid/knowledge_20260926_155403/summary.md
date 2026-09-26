| config | Hit@5 | MRR@5 | hit_paraphrase | empty_on_unanswerable | ms_per_query |
|---|---|---|---|---|---|
| dense | 0.852 | 0.759 | 1.0 | 0/3 | 398.0 |
| dense + rerank20 | 0.889 | 0.852 | 1.0 | 0/3 | 1288.0 |
| graph | 0.481 | 0.365 | 0.0 | 3/3 | 46.5 |
| hybrid rrf | 1.0 | 0.859 | 1.0 | 0/3 | 51.2 |
| hybrid rrf + rerank20 | 1.0 | 0.873 | 1.0 | 0/3 | 1093.8 |
| routed | 1.0 | 0.883 | 1.0 | 0/3 | 72.2 |
| routed + rerank20 | 1.0 | 0.895 | 1.0 | 0/3 | 1122.4 |
