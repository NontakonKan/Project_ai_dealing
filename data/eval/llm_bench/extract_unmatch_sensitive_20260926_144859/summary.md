| model | variant | f1 | precision | recall | p50_ms | p95_ms | gen_tok_s | prompt_tokens | json_error | invalid_id | no_evidence | false_rf | guard_dropped | guard_added | guard_corrected | cold_load_ms | peak_rss_mb | gpu_mem_gb | avg_cpu_pct | other_models_loaded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:latest | prompt=few_shot | 0.964 | 1.0 | 0.931 | 916.2 | 1489.8 | 54.87 | 793.95 | 0 | 0 | 0 | 0 | 1 | 1 | 3 | 544.8 | 4742 | 4.56 | 88 | 0 |
| qwen2.5:latest | prompt=few_shot_para | 0.947 | 0.964 | 0.931 | 1723.9 | 2316.2 | 54.46 | 987.95 | 0 | 0 | 0 | 0 | 2 | 1 | 7 | 558.6 | 5028 | 4.56 | 53 | 0 |
| qwen2.5:latest | prompt=few_shot_defs | 0.9 | 0.871 | 0.931 | 2573.0 | 4946.2 | 50.015 | 514 | 0 | 0 | 11 | 1 | 9 | 7 | 6 | 539.0 | 5199 | 4.56 | 85 | 0 |
