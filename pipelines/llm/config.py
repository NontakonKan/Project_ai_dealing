"""ค่าตั้งของ Local LLM แยกตามงาน (task) — แก้ที่นี่ที่เดียว / override ได้จาก CLI ตอน benchmark

เหตุผลการเลือก (M5 Pro, unified memory 24 GB) — อิงผล benchmark ใน data/eval/llm_bench/:
  - สกัด JSON -> Qwen2.5 7B: F1 0.828 (extract_profile) / 0.964 + false_rf 0 (unmatch_sensitive), p50 ~0.9-2.1 s, GPU 4.6 GB
    (Typhoon2 3B เร็วกว่า 2 เท่า ใช้ 2.3 GB แต่ F1 0.676 และแต่ง evidence บ่อย -> ใช้เป็นตัวสำรองเมื่อ RAM ไม่พอ)
  - few-shot สำคัญกว่า JSON schema: json+few_shot ≈ schema+few_shot แต่ json+zero_shot = F1 0 ทุกโมเดล (ตอบผิดรูปแบบ)
  - RAG -> Typhoon2 8B + context 1500 token: hybrid keyword_recall 0.824, cite 1.0, abstain 1.0, p50 1.4 s
    (งบ 3000 ไม่ได้ดีขึ้น แต่ช้าลง 1.6 เท่า)
  - temperature 0 สำหรับ extraction (ต้อง deterministic), 0.3 สำหรับคำตอบ (ภาษาเป็นธรรมชาติขึ้น)
"""
import os
from dataclasses import dataclass, replace

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
TIMEOUT_S = 180
RETRIES = 2


@dataclass(frozen=True)
class GenConfig:
    temperature: float = 0.0
    num_ctx: int = 4096
    num_predict: int = 512
    top_p: float = 0.9
    seed: int = 42
    keep_alive: str = "10m"

    def options(self):
        return {"temperature": self.temperature, "num_ctx": self.num_ctx, "num_predict": self.num_predict,
                "top_p": self.top_p, "seed": self.seed}


@dataclass(frozen=True)
class TaskConfig:
    model: str
    gen: GenConfig
    fmt: str = "text"            # text | json | schema (constrained decoding ด้วย JSON schema)
    prompt: str = "default"      # ชื่อ prompt variant ใน prompts.py
    context_budget: int = 0      # token สูงสุดของ context จาก retrieval (0 = ไม่ใช้)

    def with_(self, **kw):
        gen_kw = {k: kw.pop(k) for k in list(kw) if k in GenConfig.__dataclass_fields__}
        return replace(self, gen=replace(self.gen, **gen_kw), **kw)


TYPHOON_3B = "scb10x/llama3.2-typhoon2-3b-instruct"
TYPHOON_8B = "scb10x/llama3.1-typhoon2-8b-instruct"
QWEN_7B = "qwen2.5:latest"

TASKS = {
    # ป้อนข้อมูลเข้า Dense/Graph: แชท -> JSON รหัส taxonomy
    "extract_profile": TaskConfig(QWEN_7B, GenConfig(num_ctx=2048, num_predict=384), fmt="schema", prompt="few_shot"),
    "extract_unmatch": TaskConfig(QWEN_7B, GenConfig(num_ctx=1024, num_predict=256), fmt="schema", prompt="few_shot"),
    # ใช้ context จาก Dense/Graph/Hybrid
    "rag_answer": TaskConfig(TYPHOON_8B, GenConfig(temperature=0.3, num_ctx=4096, num_predict=512), context_budget=1500),
    "explain_match": TaskConfig(TYPHOON_8B, GenConfig(temperature=0.3, num_ctx=6144, num_predict=400), context_budget=2500),
}

# โมเดลที่ใช้เทียบใน benchmark (ต้อง ollama pull ไว้ก่อน)
BENCH_MODELS = [
    "qwen2.5:1.5b", "qwen2.5:3b", TYPHOON_3B, "gemma3:4b", "qwen2.5:latest", TYPHOON_8B, "gemma3:12b",
]
