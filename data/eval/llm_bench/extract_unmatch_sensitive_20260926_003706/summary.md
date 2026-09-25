| model | variant | f1 | precision | recall | p50_ms | p95_ms | gen_tok_s | prompt_tokens | json_error | invalid_id | no_evidence | false_rf | guard_dropped | guard_added | guard_corrected | cold_load_ms | peak_rss_mb | gpu_mem_gb | avg_cpu_pct | other_models_loaded |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5:latest | default | 0.964 | 1.0 | 0.931 | 852.3 | 1309.0 | 58.49 | 793.95 | 0 | 0 | 0 | 0 | 1 | 1 | 3 | 1033.1 | 4706 | 4.56 | 81 | 0 |
| scb10x/llama3.2-typhoon2-3b-instruct | default | 0.931 | 0.931 | 0.931 | 525.9 | 1672.1 | 111.125 | 713.6 | 0 | 0 | 14 | 1 | 2 | 0 | 6 | 819.6 | 2256 | 2.19 | 216 | 0 |
| scb10x/llama3.1-typhoon2-8b-instruct | default | 0.929 | 0.963 | 0.897 | 802.0 | 1224.9 | 55.68 | 713.6 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1811.7 | 4997 | 5.15 | 77 | 0 |
