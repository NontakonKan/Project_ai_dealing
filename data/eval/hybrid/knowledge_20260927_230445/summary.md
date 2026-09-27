| config | Hit@5 | MRR@5 | hit_paraphrase | empty_on_unanswerable | health_leak | ms_per_query |
|---|---|---|---|---|---|---|
| dense | 0.879 | 0.788 | 1.0 | 0/3 | 0/29 | 370.2 |
| dense + rerank20 | 0.909 | 0.879 | 1.0 | 0/3 | 1/29 | 1295.1 |
| graph | 0.394 | 0.299 | 0.0 | 3/3 | 0/29 | 47.7 |
| hybrid rrf | 1.0 | 0.87 | 1.0 | 0/3 | 0/29 | 51.6 |
| hybrid rrf + rerank20 | 1.0 | 0.896 | 1.0 | 0/3 | 1/29 | 1126.4 |
| routed | 1.0 | 0.889 | 1.0 | 0/3 | 0/29 | 68.8 |
| routed + rerank20 | 1.0 | 0.914 | 1.0 | 0/3 | 1/29 | 1152.8 |
