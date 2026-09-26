| model | variant | f1 | precision | recall | p50_ms | p95_ms | gen_tok_s | prompt_tokens | json_error | invalid_id | no_evidence | false_rf | guard_dropped | guard_added | guard_corrected | cold_load_ms | peak_rss_mb | gpu_mem_gb | avg_cpu_pct | other_models_loaded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:latest | prompt=few_shot | 0.595 | 0.611 | 0.579 | 980.3 | 1438.8 | 53.728 | 828.333 | 0 | 0 | 5 | 7 | 0 | 0 | 0 | 1068.5 | 4749 | 4.56 | 91 | 0 |
| qwen2.5:latest | prompt=few_shot_para | 0.343 | 0.375 | 0.316 | 1762.2 | 2263.6 | 56.161 | 956.5 | 0 | 0 | 7 | 10 | 0 | 0 | 0 | 562.4 | 5223 | 4.56 | 44 | 0 |
| qwen2.5:latest | prompt=few_shot_defs | 0.25 | 0.207 | 0.316 | 2550.7 | 5121.9 | 51.944 | 514 | 1 | 0 | 7 | 20 | 0 | 0 | 0 | 555.4 | 5304 | 4.56 | 80 | 0 |
