| config | Hit@5 | MRR@5 | hit_paraphrase | empty_on_unanswerable | health_leak | ms_per_query |
|---|---|---|---|---|---|---|
| dense | 0.879 | 0.788 | 1.0 | 0/3 | 0/29 | 362.5 |
| dense + rerank20 | 0.909 | 0.879 | 1.0 | 0/3 | 1/29 | 1297.7 |
| graph | 0.394 | 0.296 | 0.0 | 3/3 | 0/29 | 45.6 |
| hybrid rrf | 1.0 | 0.87 | 1.0 | 0/3 | 0/29 | 52.1 |
| hybrid rrf + rerank20 | 1.0 | 0.896 | 1.0 | 0/3 | 1/29 | 1126.8 |
| routed | 1.0 | 0.889 | 1.0 | 0/3 | 0/29 | 69.7 |
| routed + rerank20 | 1.0 | 0.914 | 1.0 | 0/3 | 1/29 | 1150.2 |
