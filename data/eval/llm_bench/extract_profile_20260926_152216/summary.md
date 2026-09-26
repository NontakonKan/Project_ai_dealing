| model | variant | f1 | precision | recall | p50_ms | p95_ms | gen_tok_s | prompt_tokens | json_error | invalid_id | no_evidence | false_rf | guard_dropped | guard_added | guard_corrected | cold_load_ms | peak_rss_mb | gpu_mem_gb | avg_cpu_pct | other_models_loaded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:latest | fmt=schema,prompt=few_shot | 0.833 | 0.875 | 0.795 | 2503.5 | 2847.1 | 49.848 | 1592.4 | 0 | 0 | 2 | 0 | 0 | 0 | 2 | 1568.3 | 6074 | 4.62 | 121 | 1 |
| scb10x/llama3.1-typhoon2-8b-instruct | fmt=schema,prompt=few_shot | 0.713 | 0.765 | 0.667 | 2306.3 | 2725.4 | 48.536 | 1455.6 | 0 | 0 | 2 | 0 | 0 | 0 | 2 | 2074.9 | 4535 | 5.29 | 100 | 0 |
| scb10x/llama3.2-typhoon2-3b-instruct | fmt=schema,prompt=few_shot | 0.634 | 0.758 | 0.545 | 1217.8 | 1525.1 | 97.284 | 1455.6 | 0 | 0 | 26 | 0 | 0 | 0 | 2 | 1085.0 | 2343 | 2.31 | 284 | 0 |
