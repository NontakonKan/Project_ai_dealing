# คำสั่งรันทีละขั้นตอน

รันจากโฟลเดอร์โปรเจกต์ทุกคำสั่ง ขั้นที่มี ✅ LLM ต้องเปิด `ollama serve` ไว้ และ**ห้ามรันพร้อมกับ benchmark** (ตัวเลขเวลาและ RAM จะเพี้ยน)

```bash
cd "/Users/develop-nontakon/Documents/ai for social/Project_dealing_psu"
```

## 0. เตรียมเครื่อง (ครั้งแรก)
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ollama list          # ต้องมี typhoon2 3b/8b, qwen2.5, gemma3, bge-m3
```

## 1. ตรวจ Taxonomy (ทุกครั้งที่แก้ taxonomy.json / concept_lexicon.json)
```bash
.venv/bin/python -m pipelines.common.validate_taxonomy
```
ควรได้ `69 ids, 0 errors, 0 warnings` ถ้ามี ERROR ต้องแก้ก่อนไปขั้นต่อไป

## 2. สร้าง Mock Data
```bash
.venv/bin/python -m pipelines.mock.run --n 300 --seed 42
```
ดู: `unmatch_reason_dist` (red_flags / appearance), `self_described_body/skin`, **`reported_appearance_on_target: 0`** (ต้องเป็น 0 เสมอ)

## 3. Ingest PDF เป็น Chunks
```bash
.venv/bin/python -m pipelines.ingest.run --chunk-size 300 --overlap 0.15
```
ดู: `data/processed/ingest_report.json` → `cleaning`, `before_after`

### 3.1 ชุดทดสอบ held-out (สำนวนที่ระบบไม่เคยเห็น) ✅ LLM
```bash
.venv/bin/python -m pipelines.eval_data.heldout_unmatch --per 2     # gemma3:12b เขียน -> ต้องตรวจ review ในไฟล์ก่อนใช้
.venv/bin/python -u -m pipelines.llm.run bench --task extract_unmatch_heldout --models qwen2.5:latest
```
หมายเหตุ: ingest จะดาวน์โหลดบทความเว็บครั้งแรก (cache ที่ `data/raw/web/`) และ OCR หนังสือครั้งแรก (cache ที่ `data/processed/ocr/`)

## 4. ตรวจคำรูปลักษณ์ + Policy (ไม่ใช้ LLM)
```bash
.venv/bin/python -c "
from pipelines.feedback import sensitive, policy
for t in ['อยากเลิกคุยเพราะอ้วนไป ดำด้วย กลิ่นตัวแรงไป', 'กินข้าวขาวกับไข่', 'หายเงียบ ไม่อธิบาย']:
    print(t, '->', sensitive.detect(t, 'unmatch'))
ex = {'red_flags':[{'id':'rf:stonewalling','severity':0.9}], 'appearance':[{'id':'body:curvy','severity':0.6}], 'hygiene':[]}
print(policy.route_unmatch(ex))
"
```
ดู: "ข้าวขาว" ต้องไม่ถูกจับ และใน `report_target` ต้องมีแค่ `rf:*`

## 5. Normalize คำเป็นรหัส
```bash
.venv/bin/python -c "
from pipelines.profile.normalize import normalize
for t in ['ฟังเพลงชิล', 'หุ่นหมี', 'ชอบเล่นบอร์ดเกม', 'ขี่ม้า']: print(normalize(t))
"   # ✅ LLM (ใช้ bge-m3 เมื่อ alias ไม่ตรง)
```
ดู: `method` (exact / contains / embedding / unmapped) คำที่ไม่เจอจะไปอยู่ใน `data/processed/unmapped_terms.jsonl`

## 6. Retrieval ชั่วคราว 3 โหมด
```bash
.venv/bin/python -c "
from pipelines.retrieval.stubs import DenseStub, GraphStub, HybridStub
q = 'คนที่เป็น anxious กับ avoidant คบกันจะเป็นอย่างไร'
for r in (DenseStub(), GraphStub(), HybridStub()):
    res = r.retrieve(q, 5); print(f'\n== {res.mode} ==')
    for it in res.items: print(f'  {it.kind:10} {it.score:<8} {it.text[:70]}')
"
```

## 7. Local LLM ✅
```bash
.venv/bin/python -m pipelines.llm.run hardware       # สเปก + โมเดลที่รันได้
.venv/bin/python -m pipelines.llm.run calibrate      # ตัวอักษรไทย/token
.venv/bin/python -m pipelines.llm.run demo           # สกัดข้อมูล + เหตุผลเลิกคุย + RAG 3 โหมด
```
ลองเหตุผลเลิกคุยเอง:
```bash
.venv/bin/python -c "
import json; from pipelines.llm import tasks
r = tasks.extract_unmatch('อยากเลิกคุยเพราะอ้วนไป ดำด้วย กลิ่นตัวแรงไป')
print('RAW   :', r['raw']); print('CLEAN :', json.dumps(r['extracted'], ensure_ascii=False))
print('ROUTED:', json.dumps(r['routed'], ensure_ascii=False)); print('STATS :', r['validation'])
"
```
ดู: `validation.misclassified_appearance` (จำนวนที่ด่านกันตัดออก), `fallback_added` (จำนวนที่ keyword เติมให้), `routed.report_target` (ต้องไม่มีรูปลักษณ์)

## 8. Benchmark ✅ (ใช้เวลานาน ให้รันทีละ task)
```bash
# 8.1 สกัดโปรไฟล์: โมเดล × config
.venv/bin/python -u -m pipelines.llm.run bench --task extract_profile \
  --models scb10x/llama3.2-typhoon2-3b-instruct,qwen2.5:latest \
  --variants "fmt=schema,prompt=few_shot;fmt=json,prompt=zero_shot" --limit 25

# 8.2 เหตุผลเลิกคุย (mock) และชุดที่ปนรูปลักษณ์ (วัด false_rf ต้องเป็น 0)
.venv/bin/python -u -m pipelines.llm.run bench --task extract_unmatch --models scb10x/llama3.2-typhoon2-3b-instruct --limit 30
.venv/bin/python -u -m pipelines.llm.run bench --task extract_unmatch_sensitive \
  --models scb10x/llama3.2-typhoon2-3b-instruct,qwen2.5:latest,scb10x/llama3.1-typhoon2-8b-instruct

# 8.3 RAG: โมเดล × Dense/Graph/Hybrid × งบ context
.venv/bin/python -u -m pipelines.llm.run bench --task rag_answer --modes dense,graph,hybrid \
  --models scb10x/llama3.1-typhoon2-8b-instruct --variants "context_budget=1500;context_budget=3000"
```
ดูผลล่าสุด:
```bash
cat "$(ls -td data/eval/llm_bench/*/ | head -1)summary.md"
```

## 9. Hybrid + Neo4j
```bash
.venv/bin/pip install -r requirements-dense.txt -r graph/requirements.txt
.venv/bin/python -m pipelines.dense.run build                     # Dense index (ChromaDB)
.venv/bin/python -m pipelines.hybrid.values_extract               # ✅ LLM ค่านิยม -> โครงสร้าง (~10 นาที)
.venv/bin/python -m pipelines.hybrid.run evaluate                 # จับคู่: Dense vs Graph vs Hybrid
.venv/bin/python -m pipelines.hybrid.run knowledge-eval           # ดึงความรู้ทุกโหมด
.venv/bin/python -m pipelines.hybrid.cases                        # เคสจริง -> data/eval/hybrid/cases.md
docker compose -f graph/compose.yaml --env-file graph/.env up -d  # Neo4j (Docker Desktop ต้องเปิด)
set -a; . graph/.env; set +a; .venv/bin/python -m graph.import_neo4j
.venv/bin/python -m unittest discover -s tests && .venv/bin/python -m unittest discover -s graph/tests
```

## 10. LINE bot (ส่วน 7)
```bash
.venv/bin/pip install -r requirements-app.txt
.venv/bin/python -m app.simulate --demo        # ✅ LLM เดโม 3 ซีน (ไม่ต้องมี token)
.venv/bin/python -m app.simulate               # พิมพ์คุยเอง: #1 #2 = กดปุ่ม
# ต่อ LINE จริง: ใส่ token ใน app/.env แล้ว
.venv/bin/uvicorn app.server:api --host 0.0.0.0 --port 8000
ngrok http 8000                                 # ตั้ง Webhook URL = https://<ngrok>/callback
```

| ขั้น | ใช้ LLM | เวลาโดยประมาณ |
|---|---|---|
| 1–4, 6 | – | ไม่กี่วินาที |
| 5, 7 | ✅ | 10–60 วินาที |
| 8 | ✅ | 5–40 นาทีต่อ task |
