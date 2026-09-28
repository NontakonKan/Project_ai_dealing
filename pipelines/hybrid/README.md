# ส่วน 4: Hybrid RAG

รวม **Dense ของฟาริก** (`pipelines/dense/`, ChromaDB + bge-m3) กับ **Graph ของบังเมษ** (`graph/`) โดยไม่ต้องแก้โค้ดของทั้งสองส่วน

## จุดร่วมของ Dense และ Graph

| จุดร่วม | Dense | Graph | Hybrid ใช้อย่างไร |
|---|---|---|---|
| **ข้อมูลต้นทาง** | `users.json` → `summaries` | `users.json` + `events` + `taxonomy` + `book_chunks` | อ่านไฟล์ชุดเดียวกัน (ส่วน 1) |
| **ID** | `user_id`, `chunk_id` | `user_id`, `chunk_id`, รหัส taxonomy | เชื่อมผลของทั้งสองฝั่งได้ตรงๆ |
| **Hard filter** | `dense.matching.eligible` | — | ใช้ตัวเดียวกันใน `context.candidates()` ทำให้ทุกโหมดมีผู้สมัครชุดเดียวกัน |
| **สิ่งที่เก่ง** | ความหมายในข้อความ รวมถึงเรื่องนอก taxonomy เช่น ค่านิยม | โครงสร้าง: สเปกตรงกับนิสัย, กฎทฤษฎี, red flag ที่ถูกรายงาน | fusion + penalty + rerank |
| **Knowledge** | `index.search("knowledge")` | `ABOUT` + `COMPATIBLE_WITH` | `HybridKnowledge` (RRF) |

Graph ใช้ `graph.build` ในหน่วยความจำ ซึ่งเป็นตัวเดียวกับที่ `import_neo4j` ใช้ จึง**ไม่ต้องเปิด Neo4j** ตอนทดลอง feature ที่คำนวณเทียบเท่ากับ query `shared` / `rule-paths` / `reports` ใน `graph/queries.py`

## ขั้นตอนการจับคู่ (`matcher.rank`)

```
candidates = hard filter (ยินยอม, เพศตรงกันสองทาง, ไม่เคย unmatch/pass)
dense  = rank() ของฟาริก (harmonic mean สองทาง − λneg·negative sim)
graph  = 0.35 prefers + 0.25 theory + 0.20 hobby + 0.10 love_language + 0.10 lifestyle
fused  = RRF หรือ α·minmax(dense) + (1−α)·minmax(graph)
final  = fused − λrf·redflag (หรือตัดออกเมื่อ hard_redflag) + w_app·appearance
rerank = top-N ผ่าน bge-reranker-v2-m3 (สองทาง) ผสมด้วย β
```

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `config.py` | `HybridConfig` (fusion, α, rrf_k, hard_redflag, λrf, λneg, w_appearance, rerank_top, β) + น้ำหนักของ Graph |
| `context.py` | โหลด users/events, DenseIndex, GraphView ครั้งเดียว + `candidates()` |
| `graph/view.py`, `graph/scorer.py`, `graph/retrieve.py`, `graph/concepts.py` | (ย้ายไปเป็นของส่วน Graph) กราฟในหน่วยความจำ, feature ของคู่ + `graph_fact`, ตัวดึงความรู้, หา concept ด้วย alias + embedding |
| `router.py` | เลือกเส้นทาง dense / graph / hybrid ตามคำถาม |
| `values_extract.py` | LLM อ่านค่านิยมจากข้อความ → `data/processed/values_structured.json` |
| `knowledge_eval.py` | วัดการดึงความรู้ (Hit@5, MRR@5) ทุกโหมด |
| `cases.py` | ค้นเคสจริงที่ Graph/Hybrid ชนะ Dense → `data/eval/hybrid/cases.md` |
| `fusion.py` | RRF / weighted + penalty + appearance |
| `reranker.py` | cross-encoder rerank (มี cache) |
| `matcher.py` | จัดอันดับ 3 โหมด: dense / graph / hybrid |
| `retrievers.py` | adapter คืน `RetrievalResult` ให้ Local LLM ใช้ได้ทันที |
| `evaluate.py` | grid เทียบ Dense vs Graph vs Hybrid ด้วย metric เดียวกับฟาริก |
| `run.py` | CLI |

## คำสั่ง

```bash
.venv/bin/pip install -r requirements-dense.txt
.venv/bin/python -m pipelines.dense.run build                     # ต้อง build Dense ก่อน
.venv/bin/python -m pipelines.hybrid.run match U002 --mode hybrid --explain
.venv/bin/python -m pipelines.hybrid.run explain U002             # Local LLM อธิบายคู่อันดับ 1
.venv/bin/python -m pipelines.hybrid.run knowledge "anxious กับ avoidant คบกันจะเป็นอย่างไร" --mode hybrid --llm
.venv/bin/python -m pipelines.hybrid.run evaluate                 # -> data/eval/hybrid/<เวลา>/summary.md
.venv/bin/python -m pipelines.llm.run bench --task rag_answer --retrievers real --modes dense,graph,hybrid
```

## ผลล่าสุด (2026-09-26)

**จับคู่** (P@5 / MRR, 288 คน): Dense 0.113 / 0.26 · Graph 0.261 / 0.55 · Hybrid ผสมคะแนน 0.247 / 0.53 · **Graph + ค่านิยมที่ LLM อ่าน 0.342 / 0.66**
**ดึงความรู้** (Hit@5 / MRR@5, 30 คำถาม): Dense 0.852 / 0.759 · Graph 0.481 / 0.365 · Hybrid 1.0 / 0.853 · **Routed + rerank 1.0 / 0.914**
บทเรียน: Dense ช่วย Hybrid ได้จริงเมื่อส่ง "ข้อมูลที่ Graph ไม่มี" (ค่านิยมนอก taxonomy) แต่ embedding แยกความหมายตรงข้ามได้แย่ → ให้ LLM อ่านเป็นโครงสร้างได้ผลดีกว่า (ถูก 97.9%)

```bash
.venv/bin/python -m pipelines.hybrid.values_extract          # ครั้งเดียว ~10 นาที
.venv/bin/python -m pipelines.hybrid.run knowledge-eval
.venv/bin/python -m pipelines.hybrid.run knowledge "..." --mode routed --llm
.venv/bin/python -m pipelines.hybrid.cases
```

## ข้อควรระวังในการตีความผล
- เฉลยมาจาก mock เป็นข้อมูลสังเคราะห์ ใช้เทียบวิธีกันเองได้ แต่ไม่ได้วัดคุณภาพการจับคู่ในโลกจริง
- ตั้งแต่ mock รุ่นที่มี `observe.py` + `values.py` ระบบเห็นแค่โปรไฟล์ที่ไม่ครบและมี noise ส่วนเฉลยใช้บุคลิกจริง และมีค่านิยมที่อยู่ในข้อความเท่านั้น (Graph มองไม่เห็น) เพื่อลดปัญหาเฉลยรั่ว
- Violation@K วัดจาก red flag จริงที่ซ่อนไว้ ระบบรู้ red flag ได้เฉพาะเมื่อมีคนรายงานตั้งแต่ 3 คน Violation จึงไม่มีทางเป็น 0 ได้จาก hard filter อย่างเดียว

## ความรู้ชุดใหม่ + แก้ป้าย concept (2026-09-27)
- เพิ่ม 3 แหล่ง (ความรักหลากมิติ, คนขี้อายเข้าสังคม, โรคติดต่อทางเพศ) ใช้ทุกหน้า -> 285 chunks
- ป้าย `ABOUT` มาจากการจับคำ: คำกำกวม (มั่นคง, หลีกเลี่ยง, การสื่อสาร, การสัมผัส, สะอาด, ความเครียด, วิตกกังวล) ต้องมีคำบริบทภายใน ±60 ตัวอักษร
  (`context_rules` ใน `data/concept_lexicon.json`) / เอกสารการแพทย์ไม่ติดป้ายความสัมพันธ์ (`tag_concepts: False`) -> ABOUT 407 -> 340 เส้น
- ลองตรวจป้ายด้วย bge-m3 และ cross-encoder แล้วแยกถูก/ผิดไม่ได้ (เช่น "ผูกพันแบบมั่นใจ (Secure)" ได้คะแนนต่ำกว่า "ระยะมั่นคง (Stability)") จึงใช้กฎบริบทแทน
- router: chunk หมวด `sexual_health` ใช้เฉพาะคำถามสุขภาพ (`HEALTH_CUES`) และไม่ใช้ในการ์ดจับคู่
- ชุดทดสอบ 36 คำถาม (+ สุขภาพ 4, เอกสารใหม่ 2) + metric `health_leak`: routed + rerank Hit@5 1.0 / MRR@5 0.914 / health_leak 1/29 -> **0/29**

## ตอบเฉพาะจากคลังความรู้ (gate.py)
- ปัญหา: คำถามที่คลังไม่มี (เช่น "คุยครั้งแรกตอนเดต") retriever ยังคืน chunk ใกล้เคียง -> LLM คัดลอกบทความเว็บที่ไม่ตรงมาตอบ
- ด่าน: cross-encoder ให้คะแนน (คำถาม, chunk) เก็บเฉพาะ >= 0.1 / graph_fact (กฎ taxonomy) ผ่านเสมอ / ไม่เหลือ = ตอบว่าไม่มีข้อมูลโดยไม่เรียก LLM
- ชุดทดสอบ 46 ข้อ (+ เรื่องที่คลังไม่ครอบคลุม 10 ข้อ): routed + gate -> ตอบว่าไม่มีข้อมูลถูก 12/12 (เดิม 0/12), Hit@5 0.971 (เสีย 1 ข้อ: "ถุงยางแตก")
- โหมดคุยเล่นห้ามให้ความรู้/อ้างอิง (ล้าง [n] และ 📚 จากประวัติแชทและคำตอบ) — เคยเลียนแบบแล้วแต่งชื่อแหล่งปลอม

## ความรู้ชุดที่ 3 + กันหลอน 2 ชั้น (2026-09-28)
- เพิ่มวิทยานิพนธ์ "บทบาทเครือข่ายสังคมออนไลน์ในการพัฒนาความสัมพันธ์แบบโรแมนติก" (นิเทศฯ จุฬาฯ 2557) ทุกหน้า -> คลัง 636 chunks
- `การสื่อสาร` นับเป็น `comm:direct` เฉพาะเมื่อมีคำว่า ตรงไปตรงมา/พูดตรง/เปิดใจ/เคลียร์ ใกล้ๆ (เดิมวิทยานิพนธ์ได้ป้ายผิด 98 chunk)
- RoutedKnowledge จำกัด 3 chunk ต่อแหล่ง: วิทยานิพนธ์ 351 chunk เคยยึด top-8 จนบทความที่ตอบตรงหลุด ("นัดเพื่อนกับแฟนวันเดียวกัน")
- `gate.verify_answer` (หลัง LLM เขียน): ตัดประโยคที่ทวนคำถาม หรือไม่มี passage ใดรองรับ (cross-encoder < 0.1) -> ไม่เหลือ = ไม่มีข้อมูล
  วัดจริง: ประโยคแต่งเกิน 0.008 / ประโยคที่มีหลักฐานจริงต่ำสุด 0.568
- ตรวจหลอนทั้งระบบ: `python -m pipelines.llm.bench.rag_judge` (เส้นทางเดียวกับบอท + gemma3:12b ตรวจทุกคำตอบ) -> `data/eval/rag_judge/`

## คลังความรู้ชุดปัจจุบัน (2026-09-28) — ตามไฟล์ใน data/
- เอาออก (ไฟล์ไม่อยู่ใน data/ แล้ว): งานวิจัยความพึงพอใจของนิสิตจุฬาฯ, หนังสือใครไม่รักช่างแม่ง, วิทยานิพนธ์เครือข่ายสังคมออนไลน์
- เพิ่ม: วิทยานิพนธ์จุฬาฯ 3 เล่ม — การสื่อสารเพื่อการเริ่มต้นความสัมพันธ์ฉันคู่รักของวัยรุ่นไทย (2549, สแกน 7 ไฟล์ -> OCR 161 หน้า),
  ความดึงดูดใจระหว่างบุคคลและรูปแบบความผูกพัน (2548), อิทธิพลของความหลงตนเองฯ ต่อการผูกมัดในความสัมพันธ์ (2553) -> รวม 908 chunks
- ingest รองรับเอกสารหลายไฟล์ (`files`), หัวบท "บทที่  1", ตรวจ OCR ที่ทวน prompt/ได้ข้อความน้อยผิดปกติแล้ว OCR ใหม่อัตโนมัติ
- ชุดทดสอบ: ข้อที่แหล่งคำตอบถูกเอาออกติด `retired` (ไม่นับ) — Q07, Q28
- คำเรียกอีกฝ่ายแทนกันได้ (`query_expand.py`): "คนคุย/เค้า/เขา/คนที่ชอบ" ค้นร่วมกับ "แฟน/อีกฝ่าย", ด่านใช้คะแนนสูงสุดของทุกแบบ,
  prompt บอก LLM ว่าเป็นคนเดียวกัน — routed + gate Hit@5 0.765 -> 0.794 / ปฏิเสธนอกเรื่อง 9/10 เท่าเดิม
- OCR วิทยานิพนธ์ 2549: ตรวจทานจากภาพทั้งหน้า บท 4 (85 หน้า) + บท 5 (15 หน้า) -> `data/ocr_verified/` (ใช้แทน OCR เสมอ)
  หน้าที่เหลือ: OCR ตัดตราดาวน์โหลด + WangchanBERTa เลือกคำจาก 2 รอบ (`pipelines/ingest/ocr_fix.py`) CER 8.0% -> 4.3%, WER 14.6% -> 11.2%
  วัดด้วย `python -m pipelines.ingest.ocr_eval` (เทียบหน้าที่ถอดด้วยมือใน data/eval/ocr_gold/)
- `verify_answer` ตรวจทีละท่อน (>= 40 ตัวอักษร) ไม่ใช่ทีละประโยค: LLM ใส่อ้างอิงครั้งเดียวท้ายย่อหน้า ท่อนที่แต่งเพิ่มเคยได้คะแนนของท่อนจริง
  (วัดจริง: "เค้าไม่ให้ความสำคัญกับความสัมพันธ์" 0.043 ถูกตัด / ท่อนถูกที่ต่ำสุดที่ผ่านเกณฑ์ 0.197)
