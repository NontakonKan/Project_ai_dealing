| model | mode | variant | keyword_recall | cite_rate | abstain_acc | ctx_tokens | p50_ms | p95_ms | gen_tok_s | credits_per_call | fallbacks | cold_load_ms | peak_rss_mb | gpu_mem_gb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| api:openai/gpt-4o-mini | hybrid | context_budget=1500 | 0.747 | 0.889 | 0.9 | 1272.667 | 1909.6 | 3379.7 | 39.947 | 1087.533 | 0 | 0.0 |  |  |
| api:deepseek/deepseek-chat | hybrid | context_budget=1500 | 0.741 | 1.0 | 0.933 | 1272.667 | 3592.5 | 9586.4 | 25.98 | 1010.167 | 0 | 0.0 |  |  |
| api:PSU-LLM/psu-gemma | hybrid | context_budget=1500 | 0.71 | 0.852 | 0.867 | 1272.667 | 559.4 | 2513.9 | 82.7 | 0 | 0 | 0.0 |  |  |
| api:deepseek/deepseek-v4-flash-0731 | hybrid | context_budget=1500 | 0.685 | 0.815 | 0.967 | 1272.667 | 5928.2 | 21836.1 | 39.38 | 1226.533 | 0 | 0.0 |  |  |
| scb10x/llama3.1-typhoon2-8b-instruct | hybrid | context_budget=1500 | 0.66 | 1.0 | 1.0 | 1272.667 | 1877.4 | 5207.5 | 52.147 |  | 0 | 2341.7 | 8621 | 5.56 |
