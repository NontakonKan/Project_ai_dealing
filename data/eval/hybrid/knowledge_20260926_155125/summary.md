| config | Hit@5 | MRR@5 | hit_paraphrase | empty_on_unanswerable | ms_per_query |
|---|---|---|---|---|---|
| dense | 0.852 | 0.759 | 1.0 | 0/3 | 439.7 |
| dense + rerank20 | 0.889 | 0.852 | 1.0 | 0/3 | 1329.6 |
| graph | 0.481 | 0.365 | 0.0 | 3/3 | 50.9 |
| hybrid rrf | 1.0 | 0.859 | 1.0 | 0/3 | 50.2 |
| hybrid rrf + rerank20 | 1.0 | 0.873 | 1.0 | 0/3 | 1095.1 |
| routed | 1.0 | 0.901 | 1.0 | 0/3 | 66.4 |
| routed + rerank20 | 1.0 | 0.914 | 1.0 | 0/3 | 1115.5 |
