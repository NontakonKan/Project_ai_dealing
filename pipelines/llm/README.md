# ส่วน 5: Local LLM (Ollama)

Local LLM ทำ 2 หน้าที่ และรองรับ Dense / Graph / Hybrid ผ่าน **สัญญากลางตัวเดียว**

```
                 ┌──────────── ป้อนข้อมูลเข้า ────────────┐
แชท LINE ──► extract_profile() ──► JSON (รหัส taxonomy) ──► Vector DB (ส่วน 2) + Graph (ส่วน 3)
เหตุผลเลิกคุย ─► extract_unmatch() ─► red_flags + severity ──► avoids / penalty (ส่วน 4)

                 ┌──────────── ใช้ context จาก ────────────┐
คำถาม ──► Dense / Graph / Hybrid .retrieve() ──► RetrievalResult ──► context.build() ──► rag_answer()
คู่ A,B ─► retrieval ของคู่นี้ ──────────────► RetrievalResult ──► context.build() ──► explain_match()
```

## สัญญากลางที่ส่วน 2/3/4 ต้องทำตาม: [retrieval/contract.py](../retrieval/contract.py)

```python
class MyDenseRetriever:          # ส่วน 2 / GraphRetriever ส่วน 3 / HybridRetriever ส่วน 4
    mode = "dense"               # "dense" | "graph" | "hybrid"
    def retrieve(self, query: str, k: int = 8) -> RetrievalResult: ...

RetrievalItem(id="research_cu2561_s09_c00", kind="chunk", text="...", score=0.82, source="dense", meta={...})
```
| kind | ใช้เมื่อ | text ควรเป็น |
|---|---|---|
| `chunk` | ความรู้จากหนังสือ/งานวิจัย | ข้อความ chunk |
| `candidate` | โปรไฟล์ผู้สมัครคู่ | `summaries.persona_text` |
| `graph_fact` | ความสัมพันธ์/เส้นทางใน Graph | ประโยคที่อ่านรู้เรื่อง เช่น `(วิตกกังวล) -[CONFLICTS_WITH]-> (หลีกเลี่ยง): วงจรไล่-หนี` |

เมื่อทำตามสัญญานี้ `tasks.rag_answer(query, my_retriever.retrieve(query))` จะใช้ได้ทันที ไม่ต้องแก้ฝั่ง LLM
ตอนนี้ใช้ [retrieval/stubs/](../retrieval/stubs/) เป็นตัวแทนชั่วคราว เมื่อของจริงเสร็จให้เอาไปแทนได้เลย

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `config.py` | โมเดล + config แยกตามงาน (temperature, num_ctx, num_predict, format, prompt, context budget) |
| `hardware.py` | ตรวจสเปกเครื่อง + ประเมินว่าโมเดลไหนรันได้ (ใช้ได้ไม่เกิน 60% ของ RAM) |
| `ollama_client.py` | เรียก Ollama + retry/error + ดึง metric (load, prompt/gen tokens, tok/s) |
| `resources.py` | วัด RAM สูงสุด / CPU ของ process Ollama และหน่วยความจำ GPU ระหว่างรัน |
| `schemas.py` | JSON schema ที่ใช้รหัส taxonomy เป็น enum (บังคับให้ตอบได้เฉพาะรหัสที่อนุญาต) |
| `prompts.py` | prompt แต่ละงาน + variant (`few_shot` / `zero_shot`, `default` / `concise`) |
| `parsing.py` | parse JSON + ด่านกันมั่ว (id ต้องอยู่ใน taxonomy, evidence ต้องมีในแชทจริง) + ตรวจการอ้างอิง |
| `context.py` | รวม context: dedupe → เรียงตามชนิด → ตัดตามงบ token |
| `tasks.py` | API ที่ส่วนอื่นเรียกใช้: `extract_profile`, `extract_unmatch`, `rag_answer`, `explain_match` |
| `bench/` | datasets (มีเฉลยจาก mock) · metrics · runner · summarize |
| `run.py` | CLI |

## คำสั่ง

```bash
ollama serve   # ถ้ายังไม่รัน
.venv/bin/python -m pipelines.llm.run hardware        # สเปก + ตารางโมเดลที่รันได้
.venv/bin/python -m pipelines.llm.run demo            # ลองทุกงาน + RAG 3 โหมด
.venv/bin/python -m pipelines.llm.run calibrate       # วัดจำนวนตัวอักษรไทยต่อ token

# benchmark งานสกัดข้อมูล: หลายโมเดล × หลาย config
.venv/bin/python -m pipelines.llm.run bench --task extract_profile \
  --models qwen2.5:3b,scb10x/llama3.2-typhoon2-3b-instruct \
  --variants "fmt=schema,prompt=few_shot;fmt=json,prompt=zero_shot" --limit 25

# benchmark RAG: โมเดล × โหมด retrieval × งบ context
.venv/bin/python -m pipelines.llm.run bench --task rag_answer --modes dense,graph,hybrid \
  --models scb10x/llama3.1-typhoon2-8b-instruct --variants "context_budget=1500;context_budget=3000"
```
ผลอยู่ที่ `data/eval/llm_bench/<task>_<เวลา>/` มี `rows.jsonl` (รายตัวอย่าง), `summary.json` และ `summary.md` (ตารางพร้อมใส่รายงาน)

## สิ่งที่วัด (ตามเกณฑ์ Level 5)

| กลุ่ม | Metric |
|---|---|
| คุณภาพการสกัด | Precision / Recall / F1 เทียบเฉลย, JSON ผิดรูปแบบ, รหัสนอก taxonomy, evidence ไม่มีในแชท |
| คุณภาพ RAG | keyword recall, อัตราการอ้างอิง [n], ความถูกต้องในการตอบว่า "ไม่มีข้อมูลเพียงพอ", จำนวน token ของ context |
| เวลา | p50 / p95 latency, tokens/sec (prompt และ generation), เวลาโหลดโมเดลครั้งแรก (cold load) |
| Resource | RAM สูงสุด, CPU เฉลี่ย, หน่วยความจำ GPU (Metal) |
| ข้อจำกัด | คำตอบถูกตัดเพราะชน num_predict, context ที่ถูกตัดทิ้งเพราะเกินงบ |


## เพิ่มเติม (2026-09-26)
- `bench/judge.py`: LLM-as-a-Judge (gemma3:12b) ให้คะแนน explain_match ด้าน faithfulness / helpfulness / tone + ตรวจด้วยกฎ (อ้างอิง, รูปลักษณ์หลุด, เปิดเผยการถูกรายงาน)
  `.venv/bin/python -u -m pipelines.llm.run bench --task explain_match --models qwen2.5:latest --limit 15`
- `extract_unmatch_heldout`: ชุดสำนวนที่ระบบไม่เคยเห็น (`pipelines/eval_data/heldout_unmatch.py`)
- `--retrievers real` ใน RAG benchmark ใช้ Dense/Graph/Hybrid ตัวจริง
