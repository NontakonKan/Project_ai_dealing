# Model comparison — PSU Dealing

## SBERT

| model | Hit@5 | MRR@5 | intent | chunk/s |
|---|---|---|---|---|
| bge-m3 (ใช้จริง) | 0.854 | 0.733 | 0.96 | 11.9 |
| e5-large | 0.902 | 0.796 | 0.947 | 6.2 |
| e5-base | 0.854 | 0.713 | 0.92 | 20.1 |
| LaBSE | 0.683 | 0.534 | 0.947 | 21.1 |
| MiniLM-L12 | 0.707 | 0.606 | 0.813 | 75.7 |

## BERT cross-encoder

| model | Hit@1 | MRR@5 | AUROC | ms/pair |
|---|---|---|---|---|
| bge-reranker-v2-m3 (ใช้จริง) | 0.744 | 0.806 | 0.827 | 82.1 |
| bge-reranker-large | 0.692 | 0.765 | 0.816 | 64.1 |
| bge-reranker-base | 0.667 | 0.75 | 0.707 | 17.8 |
| mMiniLM-L12 (mMARCO) | 0.692 | 0.755 | 0.874 | 6.4 |
| BERT-multilingual (MS MARCO) | 0.308 | 0.448 | 0.667 | 23.1 |

## LLM

| model | provider | answered | refused | grounded | keyword | cited | s p50 | credits | errors |
|---|---|---|---|---|---|---|---|---|---|
| Typhoon2 8B | local | 1.0 | 0.182 | 0.669 | 0.61 | 0.88 | 2.09 | 0 | 0 |
| Qwen2.5 7B | local | 1.0 | 0.273 | 0.762 | 0.756 | 0.918 | 3.07 | 0 | 0 |
| Gemma3 12B | local | 1.0 | 0.182 | 0.765 | 0.683 | 0.84 | 9.43 | 0 | 0 |
| Gemma3 4B | local | 1.0 | 0.091 | 0.791 | 0.732 | 0.824 | 2.55 | 0 | 0 |
| Typhoon2 3B | local | 0.951 | 0.0 | 0.531 | 0.659 | 0.62 | 1.66 | 0 | 0 |
| psu-gemma (ฟรี) | api | 0.976 | 0.455 | 0.925 | 0.683 | 1.0 | 0.8 | 0 | 0 |
| gpt-4o-mini | api | 1.0 | 0.455 | 0.801 | 0.756 | 0.936 | 2.3 | 67060 | 0 |
| deepseek-v4-flash | api | 0.976 | 0.0 | 0.883 | 0.463 | 0.49 | 6.68 | 72321 | 0 |
| qwen3.6-flash | api | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 2.09 | 55339 | 0 |
| gpt-5.6-luna (x2) | api | 1.0 | 0.273 | 0.778 | 0.683 | 0.898 | 2.88 | 142832 | 0 |
