| model | variant | f1 | precision | recall | p50_ms | p95_ms | gen_tok_s | prompt_tokens | json_error | invalid_id | no_evidence | false_rf | guard_dropped | guard_added | cold_load_ms | peak_rss_mb | gpu_mem_gb | avg_cpu_pct | other_models_loaded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:latest | default | 0.964 | 1.0 | 0.931 | 857.2 | 1308.4 | 58.415 | 793.95 | 0 | 0 | 0 | 0 | 1 | 1 | 528.1 | 4742 | 4.56 | 83 | 0 |
| scb10x/llama3.1-typhoon2-8b-instruct | default | 0.912 | 0.929 | 0.897 | 799.5 | 1228.6 | 55.605 | 713.6 | 0 | 0 | 0 | 1 | 0 | 0 | 2052.6 | 4268 | 5.15 | 78 | 0 |
| scb10x/llama3.2-typhoon2-3b-instruct | default | 0.881 | 0.867 | 0.897 | 526.9 | 1668.7 | 111.38 | 713.6 | 0 | 0 | 14 | 3 | 2 | 0 | 549.7 | 2264 | 2.19 | 220 | 0 |
