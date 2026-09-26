| model | mode | variant | keyword_recall | cite_rate | abstain_acc | ctx_tokens | p50_ms | p95_ms | gen_tok_s | cold_load_ms | peak_rss_mb | gpu_mem_gb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:latest | hybrid | context_budget=1500 | 0.857 | 1.0 | 0.933 | 1295.8 | 1914.5 | 3954.1 | 53.613 | 1557.6 | 6407 | 4.74 |
| scb10x/llama3.1-typhoon2-8b-instruct | hybrid | context_budget=1500 | 0.607 | 0.929 | 1.0 | 1295.8 | 1314.2 | 2216.6 | 54.527 | 874.7 | 8312 | 5.56 |
| scb10x/llama3.1-typhoon2-8b-instruct | graph | context_budget=1500 | 0.571 | 0.857 | 0.933 | 562.933 | 1253.0 | 2069.6 | 54.647 | 874.7 | 8312 | 5.56 |
| qwen2.5:latest | dense | context_budget=1500 | 0.524 | 1.0 | 0.867 | 1333.067 | 2920.7 | 3761.1 | 53.94 | 1557.6 | 6407 | 4.74 |
| qwen2.5:latest | graph | context_budget=1500 | 0.5 | 1.0 | 0.733 | 562.933 | 1689.4 | 3959.3 | 54.72 | 1557.6 | 6407 | 4.74 |
| scb10x/llama3.1-typhoon2-8b-instruct | dense | context_budget=1500 | 0.476 | 1.0 | 1.0 | 1333.067 | 1662.6 | 2754.2 | 54.493 | 874.7 | 8312 | 5.56 |
