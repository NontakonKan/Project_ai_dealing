# Project_ai_dealing

LINE OA chatbot หาคู่: ผู้ใช้คุยเล่นกับ AI เรื่องกิจวัตรและสเปกที่ชอบ ระบบเก็บเป็นบุคลิก แล้วใช้ Hybrid RAG (Dense + Graph) จับคู่
ถ้าเลิกคุยกับใคร ระบบจะจำสิ่งที่ไม่ชอบไว้ และลดคะแนนคนที่มีลักษณะแบบนั้นในการจับคู่ครั้งถัดไป

> README นี้เขียนให้ **คนทำส่วน 2 (Dense RAG)** และ **ส่วน 3 (Graph RAG)**: ข้อมูลส่วน 1 พร้อมแล้ว ใช้อะไรได้ อยู่ไฟล์ไหน และมีกติกาอะไร

---

## 1. เริ่มต้นใช้งาน (คำสั่งทีละขั้นอยู่ใน [RUN.md](RUN.md))

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pipelines.mock.run              # สร้าง data/mock/ ใหม่ (seed 42 ได้ผลเหมือนเดิมทุกครั้ง)
.venv/bin/python -m pipelines.ingest.run            # สร้าง data/processed/ ใหม่
```

ส่วน Dense ใช้ ChromaDB เก็บเวกเตอร์แบบถาวรใน `data/chroma_db/` (โฟลเดอร์นี้ไม่ขึ้น Git):

```bash
python -m pip install -r requirements-dense.txt
python -m pipelines.dense.run build
python -m pipelines.dense.run match U002 --top-k 5
python -m pipelines.dense.run evaluate
```

รายละเอียดการค้นและการตั้งค่า LLM ดูที่ [pipelines/dense/README.md](pipelines/dense/README.md)

ไม่ต้องรันก็ได้ ไฟล์ผลลัพธ์อยู่ใน repo แล้ว รันใหม่เมื่อ taxonomy หรือ config เปลี่ยน

---

## 2. ภาพรวม

```
                 data/taxonomy.json  (รหัสกลาง เช่น rf:stonewalling, attach:secure)
                        │                          │
          ① pipelines/mock                ② pipelines/ingest
          (ผู้ใช้จำลอง 300 คน)               (งานวิจัย/หนังสือ PDF)
                        │                          │
     data/mock/users.json, events.jsonl    data/processed/book_chunks.jsonl
                        └───────────┬──────────────┘
                                    ▼
                  ส่วน 2: Vector DB      ส่วน 3: Knowledge Graph
                                    ▼
                          ส่วน 4: Hybrid RAG
```

**หัวใจของส่วน 1 คือ `data/taxonomy.json`:** ทุกอย่างใช้รหัสชุดเดียวกัน
ไม่ว่าผู้ใช้จะพิมพ์ "หายเงียบ" หรือหนังสือเขียนถึง Silent treatment จะกลายเป็น `rf:stonewalling` เหมือนกัน
**อย่าสร้าง label ใหม่เอง** ถ้าต้องการรหัสใหม่ให้เพิ่มใน taxonomy.json

---

## 3. ไฟล์ข้อมูลที่ใช้ได้

| ไฟล์ | จำนวน | คืออะไร | ส่วน 2 ใช้ | ส่วน 3 ใช้ |
|---|---|---|---|---|
| `data/taxonomy.json` | 69 รหัส + 14 กฎ | รหัสกลาง + กฎความเข้ากันได้ | – | ✅ node ของ Trait/RedFlag + edge ระหว่าง Trait |
| `data/mock/users.json` | 300 คน | โปรไฟล์ผู้ใช้ | ✅ embed `summaries` | ✅ node User + edge |
| `data/mock/events.jsonl` | 432 | เลิกคุย / แมตช์ / กดผ่าน | ✅ negative examples | ✅ edge UNMATCHED |
| `data/processed/book_chunks.jsonl` | 129 chunk | ความรู้จาก 10 แหล่ง: งานวิจัย 44 / หนังสืออกหัก (OCR) 13 / สไลด์ครองใจคน 27 / บทความเว็บ 7 เรื่อง 45 | ✅ embed `text` | ✅ node BookChunk |
| `data/mock/ground_truth_pairs.json` | 286 คน | **เฉลย** การจับคู่ | 📏 ใช้วัดผลเท่านั้น | 📏 ใช้วัดผลเท่านั้น |
| `data/mock/chats.jsonl` | 100 | แชทจำลอง + เฉลยการสกัด | – | – (ใช้ทดสอบ extractor) |

---

## 4. กติกาสำคัญ ⚠️

1. **ห้ามใช้ field ที่ขึ้นต้นด้วย `_`** (`_ground_truth_flags`, `_ground_truth_appearance`, `_archetype`) ในการ retrieval
   field กลุ่มนี้คือคำตอบที่ซ่อนไว้ ถ้านำมาใช้ ผลทดลองจะดีเกินจริงและนับไม่ได้
2. **`reported_traits` (สิ่งที่คนอื่นรายงานว่าผู้ใช้คนนี้มี) ใช้ได้เฉพาะรายการที่ `usable: true`** คือมีคนรายงานตั้งแต่ 3 คนขึ้นไป เพื่อกันการกลั่นแกล้ง
3. **Hard filter ก่อนจัดอันดับเสมอ:**
   - `consent.matching == true`
   - เพศตรงกันทั้งสองทาง: `A.gender ∈ B.seeking` และ `B.gender ∈ A.seeking`
   - ไม่เอาตัวเอง และไม่เอาคนที่เคยมี event `unmatch` / `pass` กับเราแล้ว
4. **ห้าม `ground_truth_pairs.json` เข้าไปอยู่ใน pipeline** ใช้แค่ตอน evaluate
5. **รูปลักษณ์ (รูปร่าง/สีผิว/สุขอนามัย) = สเปกส่วนตัว** ดู `appearance_policy` ใน taxonomy.json และ [feedback/policy.py](pipelines/feedback/policy.py)
   - ข้อมูลรูปลักษณ์ของผู้สมัคร: ใช้ได้เฉพาะ `appearance.self_described` (เจ้าตัวบอกเอง สีผิวต้องมี `consent_sensitive`)
   - สเปกรูปลักษณ์ของผู้ใช้ (`wants`/`avoids` ที่ขึ้นต้นด้วย `body:` `skin:` `hygiene:`) ใช้เป็น **soft score** ผ่าน `policy.appearance_score()` น้ำหนัก `w_appearance` เท่านั้น ห้ามใช้เป็น hard filter
   - **ห้าม embed รูปลักษณ์ลง Vector** (`summaries` ถูกกรองรูปลักษณ์ออกแล้ว) ไม่อย่างนั้น Dense penalty จะเรียนรู้รูปลักษณ์แบบตรวจสอบไม่ได้
   - `reported_traits` มีได้แค่ `rf:*` ไม่มีทางมีรูปลักษณ์ (เหตุผลเลิกคุยเรื่องรูปลักษณ์เก็บที่ผู้พูดเท่านั้น)

---

## 5. Schema ที่ต้องรู้

### 5.1 User (`users.json`)
```jsonc
{
  "user_id": "U002",
  "demographic": { "age": 23, "gender": "F", "seeking": ["M"], "faculty": "ทันตแพทยศาสตร์" },
  "persona": {
    "hobbies":  [{ "id": "hobby:movies", "confidence": 0.65, "evidence_count": 5, "last_seen": "2026-08-22" }],
    "traits":   [{ "id": "trait:logical", "confidence": 0.74, "evidence_count": 4 }],
    "lifestyle": { "sleep": "late", "social_energy": "low", "weekend": "stay_home" },
    "comm_style": [{ "id": "comm:direct", "confidence": 0.84 }],
    "attachment_style": { "id": "attach:avoidant", "confidence": 0.4 },
    "love_language": [{ "id": "ll:words", "confidence": 0.71 }],
    "love_components": { "intimacy": 4, "passion": 5, "commitment": 3 },   // Sternberg 1–5
    "life_satisfaction": 5
  },
  "preferences": {
    "wants":  [{ "id": "trait:funny", "weight": 0.94 },                      // สเปกที่อยากได้
               { "id": "skin:fair", "weight": 0.6 }],                         // สเปกรูปลักษณ์ (soft score)
    "avoids": [{ "id": "rf:stonewalling", "weight": 0.99, "source": "breakup:E0001", "count": 1 },
               { "id": "body:curvy", "weight": 0.58, "source": "breakup:E0036", "count": 1 }]
  },
  "appearance": {                                                             // เจ้าตัวระบุเอง
    "self_described": [{ "id": "body:average", "source": "self" }, { "id": "skin:tan", "source": "self" }],
    "consent_sensitive": true                                                 // ยินยอมเปิดเผยสีผิว (PDPA ม.26)
  },
  "reported_traits": [{ "id": "rf:stonewalling", "report_count": 2, "usable": false }],
  "summaries": {
    "persona_text":    "อายุ 23 ปี ... นิสัย: ติดบ้าน, ตลก ...",   // ตัวตนของฉัน
    "preference_text": "อยากได้คนที่ ตลก อารมณ์ดี, มีเหตุผล ...",   // สเปกที่ฉันอยากได้
    "avoid_text":      "ไม่ชอบคนที่ เงียบใส่/หายไปเวลามีปัญหา"      // สิ่งที่ไม่ชอบ
  },
  "profile_completeness": 0.86,
  "consent": { "matching": true }
}
```
- `avoids.weight` สะสมทุกครั้งที่เลิกคุยด้วยเหตุผลเดิม ด้วยสูตร `w_new = 1 − (1 − w_old)(1 − severity)` ยิ่งเจอบ่อยยิ่งเข้าใกล้ 1
- `avoids.source`: `"stated"` = ผู้ใช้บอกเอง, `"breakup:Exxxx"` = ได้มาจากการเลิกคุย

### 5.2 Event (`events.jsonl`)
```json
{"event_id": "E0036", "type": "unmatch", "from_user": "U026", "about_user": "U251",
 "timestamp": "2026-08-30T08:00:00", "raw_reason": "ไม่ไปต่อละ ขี้เหวี่ยง มีกล้ามไป แบบนี้ไม่ใช่เลย",
 "gold_extracted": {"red_flags":  [{"id": "rf:hot_temper", "severity": 0.67}],   // -> A.avoids + B.reported_traits
                    "appearance": [{"id": "body:athletic", "severity": 0.58}], // -> A.avoids เท่านั้น
                    "hygiene":    []}}                                          // -> A.wants (ดูแลตัวเอง)
```
`type` มี 3 ค่า: `unmatch` (เลิกคุย) / `matched` (คุยกันได้ดี) / `pass` (กดผ่าน)

### 5.3 Book chunk (`book_chunks.jsonl`)
```json
{
  "chunk_id": "research_cu2561_s09_c00",
  "source_id": "research_cu2561", "doc_type": "research",
  "chapter": 2, "section_title": "ทฤษฎีสามเหลี่ยมความรัก (Triangular theory of love)",
  "pages": [19, 20, 21],
  "text": "Sternberg (1986) ได้เสนอทฤษฎีสามเหลี่ยมความรัก ...",
  "n_words": 290,
  "category": "theory",
  "concepts": ["love:intimacy", "love:commitment", "love:passion"],
  "topics": ["love_theory"],
  "target_trait": []
}
```
- `category` มี 4 ค่า: `abstract` / `background` / `theory` / `finding_discussion`
- chunk ละประมาณ 300 คำ (นับด้วย PyThaiNLP) ซ้อนกันประมาณ 45 คำ และไม่ตัดข้ามหัวข้อ
- `doc_type` มี `research` / `book` / `slides` และ `category` เพิ่ม `breakup_recovery` (หนังสือ) กับ `interpersonal_skills` (สไลด์)
- หนังสือ "ใครไม่รักช่างแม่ง" เป็นไฟล์สแกน จึง OCR ด้วย **qwen2.5vl ผ่าน Ollama** แล้วเก็บ cache ไว้ที่ `data/processed/ocr/` (หน้าที่โมเดลตอบข้อความของตัวเองจะถูก OCR ซ้ำหรือตัดทิ้ง)

---

## 6. สำหรับส่วน 2: Dense RAG

### ต้อง embed อะไร
| Collection | ข้อความ | metadata สำหรับ filter |
|---|---|---|
| `persona_vec` | `summaries.persona_text` | `user_id, gender, seeking, age, consent` |
| `preference_vec` | `summaries.preference_text` | เหมือนด้านบน |
| `avoid_vec` | `summaries.avoid_text` (ข้ามถ้าว่าง) | `user_id` |
| `knowledge_vec` | `book_chunks.text` | `category, concepts, topics, source_id` |

### การจับคู่ต้องทำสองทาง (ไม่สมมาตร)
```
score(A,B) = combine( sim(A.preference_vec, B.persona_vec),   # B ตรงสเปก A ไหม
                      sim(B.preference_vec, A.persona_vec) )   # A ตรงสเปก B ไหม
combine = harmonic mean (แนะนำ: ถ้าฝั่งใดฝั่งหนึ่งต่ำ คะแนนรวมจะต่ำตาม)
```

### Penalty จากการเลิกคุย (ฝั่ง Dense)
ให้เก็บ `persona_vec` ของคนที่ A เคย `unmatch` ไว้เป็น negative examples แล้วหักคะแนนผู้สมัครที่คล้ายคนเหล่านั้น:
```
penalty(A,B) = max_sim(B.persona_vec, negatives_of_A)
final = score − λ · penalty        # λ คือค่าที่ต้องจูนในการทดลอง
```

### ดึงคำแนะนำจากหนังสือ
ใช้ `concepts` เป็น pre-filter ก่อนแล้วค่อยทำ vector search เช่น คู่นี้เสี่ยง `rf:stonewalling` ก็ filter `concepts CONTAINS "rf:stonewalling"` หรือใช้ `category = "theory"` สำหรับคำถามเชิงทฤษฎี

### สิ่งที่ต้องทดลอง (เพื่อ Level 5)
Top-K ∈ {5, 10, 20} × similarity threshold × มี/ไม่มี Cross-Encoder rerank × λ ของ penalty
(สเปกรูปลักษณ์ไม่ใช่งานของ Dense ให้ส่วน 4 บวกเพิ่มด้วย `policy.appearance_score()` ตอน fusion และลองหลายค่า `w_appearance` เช่น 0 / 0.1 / 0.2 / 0.3)
วัดด้วย Precision@K, Recall@K, MRR เทียบกับ `ground_truth_pairs.json`

---

## 7. สำหรับส่วน 3: Graph RAG

### Node
| Label | มาจาก | property |
|---|---|---|
| `User` | users.json | `user_id, age, gender, seeking, consent` |
| `Trait` `Hobby` `CommStyle` `Attachment` `LoveLanguage` `RedFlag` `LoveComponent` | taxonomy.json | `id, label_th, source` |
| `BodyType` `SkinTone` `Hygiene` | taxonomy.json | `id, label_th, sensitive` |
| `BookChunk` | book_chunks.jsonl | `chunk_id, category, section_title` (text เก็บใน Vector DB แล้วอ้างถึงด้วย chunk_id) |

### Edge
| Edge | มาจาก | property |
|---|---|---|
| `(User)-[:HAS_TRAIT]->(Trait/CommStyle/Attachment)` | `persona.*` | `confidence` |
| `(User)-[:LIKES]->(Hobby)` | `persona.hobbies` | `confidence, evidence_count` |
| `(User)-[:PREFERS]->(Trait)` | `preferences.wants` | `weight` |
| `(User)-[:AVOIDS]->(RedFlag)` | `preferences.avoids` | `weight, count, source` |
| `(User)-[:REPORTED_AS]->(RedFlag)` | `reported_traits` **เฉพาะ usable** | `report_count` |
| `(User)-[:SELF_DESCRIBED]->(BodyType/SkinTone)` | `appearance.self_described` (**แหล่งเดียว**ของรูปลักษณ์ผู้สมัคร) | `source: "self"` |
| `(User)-[:PREFERS / AVOIDS {kind:"appearance"}]->(BodyType/SkinTone/Hygiene)` | `wants`/`avoids` ที่เป็นรูปลักษณ์ | `weight` (ใช้เป็น soft score เท่านั้น) |
| `(User)-[:UNMATCHED / MATCHED / PASSED]->(User)` | events.jsonl | `event_id, timestamp` |
| `(X)-[:COMPATIBLE_WITH / CONFLICTS_WITH / OPPOSITE_OF]->(Y)` | `taxonomy.compatibility_rules` | `weight, reason, source` |
| `(BookChunk)-[:ABOUT]->(Trait/RedFlag/Attachment/LoveComponent)` | `chunk.concepts` | `count` จาก `concept_counts` |

### ตัวอย่าง query
```cypher
// Hard constraint: ตัดคนที่ถูกรายงานว่ามี red flag ที่ A หลีกเลี่ยง
MATCH (a:User {user_id:$uid})-[:AVOIDS]->(rf:RedFlag)<-[:REPORTED_AS]-(b:User)
RETURN collect(b.user_id) AS excluded

// Multi-hop: ความเข้ากันได้เชิงทฤษฎี (A มี trait ที่เข้ากับ trait ของ B)
MATCH (a:User {user_id:$uid})-[:HAS_TRAIT]->(t1)-[r:COMPATIBLE_WITH]-(t2)<-[:HAS_TRAIT]-(b:User)
WHERE a <> b
RETURN b.user_id, sum(r.weight) AS theory_score ORDER BY theory_score DESC

// Explain: ดึงความรู้จากหนังสือที่อธิบาย red flag หรือ trait ของคู่นี้
MATCH (a:User {user_id:$uid})-[:AVOIDS]->(rf)<-[:ABOUT]-(c:BookChunk) RETURN c.chunk_id
```

### จุดที่ Graph ต้องชนะ Dense ให้ได้ (ต้องแสดงในรายงาน)
- **Red flag ซ่อนอยู่:** ข้อความ persona ของสองคนคล้ายกันมาก แต่ B ถูกรายงานว่า `rf:stonewalling` ซึ่ง A หลีกเลี่ยงอยู่ → Dense ให้คะแนนสูง แต่ Graph ตัดออก
- **ความเข้ากันได้เชิงทฤษฎี:** `attach:anxious` กับ `attach:avoidant` เป็น `CONFLICTS_WITH` → ข้อความไม่ได้บอกตรงๆ แต่ Graph มองเห็นผ่าน multi-hop

---

## 8. การวัดผล (ใช้ร่วมกันทุกส่วน)

`ground_truth_pairs.json`:
```json
{"user_id": "U001",
 "relevant": [{"user_id": "U145", "score": 0.61}, ...],   // top-5 คู่ที่ควรแมตช์
 "must_exclude": ["U087", ...]}                            // มี red flag ที่ U001 หลีกเลี่ยง -> ต้องไม่ติดอันดับ
```
| Metric | วัดอะไร |
|---|---|
| Precision@K / Recall@K / MRR / nDCG | จัดอันดับถูกไหม (เทียบกับ `relevant`) |
| **Violation@K** | สัดส่วนคนใน `must_exclude` ที่หลุดมาอยู่ใน top-K (ต้องใกล้ 0) → ใช้พิสูจน์ว่า penalty ทำงาน |

ให้ทุกส่วนรายงานในตารางเดียวกัน: **Dense-only vs Graph-only vs Hybrid**

---

## 8.5 สัญญากลางของ Retrieval (ส่วน 2/3/4 ต้องทำตาม) ⚠️

Local LLM (ส่วน 5) รับ context จาก retriever ทุกตัวในรูปแบบเดียวกัน ดู [pipelines/retrieval/contract.py](pipelines/retrieval/contract.py)
```python
class DenseRetriever:            # หรือ GraphRetriever / HybridRetriever
    mode = "dense"
    def retrieve(self, query: str, k: int = 8) -> RetrievalResult: ...
# item: RetrievalItem(id, kind="chunk"|"candidate"|"graph_fact", text, score, source, meta)
```
- Graph ให้คืน `graph_fact` เป็นประโยคที่อ่านรู้เรื่อง เช่น `(วิตกกังวล) -[CONFLICTS_WITH]-> (หลีกเลี่ยง): วงจรไล่-หนี`
- ระหว่างที่ของจริงยังไม่เสร็จ ใช้ตัวแทนชั่วคราวใน [pipelines/retrieval/stubs/](pipelines/retrieval/stubs/)
- รายละเอียดฝั่ง LLM และ benchmark: [pipelines/llm/README.md](pipelines/llm/README.md)

## 9. โครงสร้างโค้ด

```
data/
  taxonomy.json  concept_lexicon.json          รหัสกลาง / คีย์เวิร์ดสำหรับ tag chunk
  งานวิจัยการหาคู่.pdf  หนังสือใครไม่รักช่างแม่ง_ใช้ตอนอกหัก.pdf
  mock/        users, events, chats, ground_truth_pairs, data_report
  processed/   book_chunks, sections, ingest_report
pipelines/
  common/   paths, io_utils, taxonomy, validate_taxonomy   ใช้ร่วมกัน (+ ตัวตรวจ taxonomy)
  feedback/ sensitive, policy, apply                  เหตุผลเลิกคุย -> เก็บที่ไหน (พฤติกรรม vs รูปลักษณ์)
  profile/  normalize                                 คำอิสระ -> รหัส taxonomy (alias -> embedding -> unmapped)
  mock/     config, users, events, summaries, chats, compat, ground_truth, report, run
  ingest/   sources, extract, ocr, clean, sectioner, chunker, tagger, report, run
  retrieval/ contract (สัญญากลาง) + stubs/ (dense, graph, hybrid ชั่วคราว)
  llm/      config, hardware, ollama_client, resources, schemas, prompts, parsing, context, tasks, run + bench/
  hybrid/   matcher, fusion, router, reranker, retrievers, values_extract, evaluate, knowledge_eval, cases
app/        ส่วน 7 LINE OA: server (webhook), handlers, intent, flows/, profile, live, storage, flex, simulate
```
- โหลดข้อมูลด้วย helper เดิมได้: `from pipelines.common.io_utils import read_json, read_jsonl`
- รายละเอียดแต่ละโมดูลดูที่ [pipelines/README.md](pipelines/README.md)
- **กติกาโค้ด:** แยกไฟล์ตามหน้าที่ ห้ามเขียนทั้ง pipeline จบในไฟล์เดียว

## สถานะส่วน 1
- ✅ Taxonomy, mock users/events/chats, ground truth, ingest 10 แหล่ง (129 chunks) รวม OCR หนังสือด้วย qwen2.5vl + แก้คำผิด 63 จุด (`data/ocr_corrections.json`)
- ✅ red flag ครบ 10/10 และ attachment ครบ 4/4 มี chunk อธิบาย (เพิ่มบทความคณะจิตวิทยา จุฬาฯ)
- ✅ ชุดทดสอบ held-out `data/eval/unmatch_heldout.json` (สำนวนที่ระบบไม่เคยเห็น 18 ข้อ)
- ⏳ หนังสือฉบับเต็ม (ตอนนี้มีฉบับตัวอย่าง 27 หน้า)
- ⏳ Pipeline สกัดข้อมูลจากแชทจริง (LINE → LLM → JSON → merge เข้าโปรไฟล์)

## ส่วน Graph

โค้ดสร้าง Knowledge Graph และสำรวจ Neo4j อยู่ใน [`graph/`](graph/README.md)
รัน `python3 -m graph.build` เพื่อตรวจข้อมูล และ `python3 -m graph.import_neo4j` เพื่อนำเข้าฐานข้อมูลโดยตรง
ดูกราฟและ export ภาพหรือข้อมูลผ่าน Neo4j Browser โดยใช้ `graph/queries.cypher`
มี schema, validation, การนำเข้าแบบ snapshot และคำสั่ง Cypher พร้อมเลขหน้าเอกสารอ้างอิง
ส่วนนี้ยังไม่มี RAG, embeddings หรือระบบจัดอันดับคู่

## ส่วน 7 System Integration (LINE)
ดู [app/README.md](app/README.md) — ทดสอบในเครื่องได้ทันทีด้วย `python -m app.simulate --demo` (เดโม 3 ซีนจาก req.md) และต่อ LINE จริงด้วย `app/.env` + `uvicorn app.server:api` + `ngrok http 8000`
