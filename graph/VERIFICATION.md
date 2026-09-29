# ผลตรวจ Graph

ตรวจข้อมูลและโค้ดวันที่ 29 กันยายน 2026 โดยแก้เฉพาะ `graph/`

## ข้อมูลที่ build และนำเข้า Neo4j

| รายการ | จำนวน |
|---|---:|
| Nodes | 1,446 |
| Relationships | 8,252 |
| Users จำลอง | 300 |
| Concepts จาก taxonomy | 69 |
| Sources | 37 |
| BookChunks | 1,035 |
| NEXT_CHUNK | 685 |
| Claims / SUBJECT / SUPPORTED_BY | 5 / 5 / 5 |
| human_verified Claims | 0 |

Snapshot: `b5f0d72d1d12d71f7dfd6d0db6361be4b2086419f75dbd534de39c87f5a44c45`

ใช้ Neo4j Community 5.26 ใน Docker ที่พอร์ตมาตรฐาน localhost **7474 / 7687**
ข้อมูล Claims มาจาก `graph/knowledge_claims.jsonl` เมื่อไม่มีไฟล์ override ใน `data/processed/`
ทุก quote/object/qualifier ตรวจตรงกับต้นฉบับและ source hash แต่ Claims ทั้ง 5 ยังเป็นข้อเสนอที่ไม่ผ่านการยืนยันโดยคน
ไม่คืนข้อเสนอเหล่านี้เป็น `graph_fact`; คืนช่วงข้อความต้นฉบับสำหรับค้นและอ้างอิงเท่านั้น

## การทดสอบที่ผ่าน

```bash
set -a
. graph/.env
set +a
GRAPH_NEO4J_TEST=1 .venv/bin/python -m unittest discover -s graph/tests
.venv/bin/python -m unittest discover -s tests
```

**Graph 52 tests ผ่าน รวม 4 tests กับ Neo4j จริง ไม่มี skip; แอป 86 tests ผ่าน**
ครอบคลุม source hashes และ quotes, subject/object/predicate, polarity/qualifier, การแยกสถานะตรวจทาน,
source spans ที่รักษาข้อจำกัดในย่อหน้า, Hybrid ที่เก็บช่วงหลักฐานแยกจาก chunk เต็ม,
การไม่เพิ่มคะแนนจาก Claims ซ้ำ, lexical fallback สำหรับแง่มุมอื่น, document neighbours และ source introduction
การทดสอบฐานข้อมูลตรวจ import ซ้ำ, ทุก query, active snapshot เมื่อข้อมูลเปลี่ยน และอ่านเส้น Claim กลับพร้อม quote/status

การสกัดแบ่งบรรทัด OCR ยาวเป็นช่วงต้นฉบับซ้อนกัน ทำให้มี passage ใช้สกัดได้ใน 1,035/1,035 chunks
จากเดิม 887/1,035 chunks; ตัวเลขนี้วัด coverage ของข้อความ ไม่ใช่ความแม่นยำการสกัด Claims

## ผลค้นคืนหลักฐานตรงตาม chunk ID

```bash
.venv/bin/python -m graph.evaluate_claims --evidence-benchmark
# ต้องเปิด Ollama สำหรับการสร้างคำตอบด้วย Typhoon2 8B local
.venv/bin/python -m graph.evaluate_claims --evidence-benchmark --generate
```

แสดงผลใน terminal โดยไม่สร้างไฟล์ทดลองหรือเขียน ChromaDB
ชุดคำถามเป้าหมายมี 5 ข้อและคำถามนอกคลัง 1 ข้อ:

| ตัวดึง | Hit@8 | MRR@8 |
|---|---:|---:|
| Dense | 0.40 | 0.200 |
| Graph ไม่มี Claims | 0.60 | 0.300 |
| Graph มี Claims | 1.00 | 0.900 |
| Routed Hybrid | 1.00 | 0.350 |

ตัวอย่าง: `secure attachment รับความช่วยเหลือจากคนอื่นอย่างไร`
Dense และ Graph ที่ไม่มี Claims ไม่พบ chunk เป้าหมายใน top 8
Graph เดิน `attach:secure ← SUBJECT — Claim — SUPPORTED_BY → web_chula_attachment_s00_c02`
แล้วดึงย่อหน้าที่ระบุว่าเต็มใจพึ่งพาและรับการสนับสนุนจากผู้อื่น
Typhoon2 8B ตอบเนื้อหานี้พร้อม `[1]` โดยอ้างถึง source excerpt ของ Claim และผ่าน relevance/answer gates เดิม
Routed Hybrid ที่ใช้ตัวค้นของแอปตอบคำถามนี้ได้เช่นกัน; ก่อนแยกรหัสช่วงข้อความออกจาก chunk เต็ม เคยตอบว่าไม่มีข้อมูล

ทดสอบ Routed Hybrid กับ `Ghosting ทำไมความรู้สึกแย่ถึงค้างนาน` แล้วตอบจากบทนำของเอกสาร Thai PBS พร้อม `[1]` ได้
บทนำถูกกู้ผ่าน Source/HAS_CHUNK เพื่อประกอบนิยามกับผลศึกษาที่อยู่ใน chunk หลัง
ผลนี้แสดงว่า Graph ช่วยกู้หลักฐานและบริบทที่การจัดอันดับ Dense อย่างเดียวพลาด
การเพิ่ม node/relationship เพียงอย่างเดียวไม่ใช่เหตุผลของคะแนน: ต้องแสดงเส้นค้น, ข้อความที่ส่ง และคำตอบที่อ้างข้อความนั้น

## ผลชุดคำถามกว้างเดิม

```bash
.venv/bin/python -m graph.evaluate_claims --retrieval-benchmark
```

52 ข้อ: มีคำตอบ 41 ข้อ ไม่มีคำตอบ 11 ข้อ; ใช้ keyword heuristic กับข้อความต้นฉบับเต็มของ chunk:

| ตัวดึง | Hit@8 | MRR@8 |
|---|---:|---:|
| Graph แบบ ABOUT tags เดิม | 0.122 | 0.064 |
| ค้นข้อความอย่างเดียว ไม่มี Claims/ABOUT/NEXT_CHUNK | 0.829 | 0.649 |
| Graph ไม่มี Claims | 0.829 | 0.655 |
| Dense | 0.707 | 0.602 |
| Graph มี Claims | 0.829 | 0.647 |
| Hybrid RRF | 0.878 | 0.634 |

Claims ไม่เพิ่ม Hit@8 ในชุดกว้างนี้ และ MRR ของ Graph ลดเล็กน้อย
จึงสรุปได้เฉพาะว่ามีประโยชน์ในคำถามเป้าหมายที่สาธิต ไม่ใช่ดีกว่าทุกหัวข้อ
เวลาค้นเปลี่ยนตามโหลดเครื่องและการเรียกโมเดลพร้อมกัน; ไม่ใช้รอบนี้เป็น latency benchmark ของ production

## ข้อจำกัดและการประเมินตามเกณฑ์

ตามเกณฑ์ Graph RAG ระดับ 5 ที่ให้มา ระบบมีโครงสร้างสัมพันธ์ที่มีความหมาย, เส้นค้นที่ย้อนถึงต้นฉบับ,
ตัวอย่างส่งหลักฐานเข้า LLM และการเปรียบเทียบที่อธิบายข้อจำกัดของ Dense ได้
เป็นหลักฐานรองรับการเสนอระดับ 5 ในด้าน Graph RAG; คะแนนจริงยังขึ้นกับผู้ประเมินและการสาธิต

ชุด 5 ข้อเลือกจาก Claims ที่มีอยู่ และชุด 52 ข้อใช้ระหว่างพัฒนา จึงไม่ใช่ held-out หรือ blind human evaluation
Hit@8 และหมายเลข citation ที่อยู่ในช่วงไม่ได้ยืนยันว่าเนื้อหาทุกประโยคถูกต้องหรือ cite ถูก passage ทางความหมาย
ยังพบการตอบไม่ตรงประเด็นบางคำถามและการปฏิเสธตอบจาก relevance gate แม้ดึง chunk เป้าหมายมาได้
ยังไม่มีการประเมินครอบคลุมทุกแหล่งหรือการตรวจโดยคนครบทุก Claim

การทดสอบคำตอบใช้โมเดล local และ primitive เดิมของ pipeline แต่ไม่ทดสอบ LINE webhook,
conversation history, API LLM หรือ topic rewrite รอบสอง; ไม่อ้างว่าทั้งโปรเจกต์ได้ระดับ 5
การใช้ quote ยืนยันที่มาได้ แต่ไม่แทนการตรวจความหมายของ subject/predicate/object โดยคน
กฎ compatibility จาก taxonomy ยังคงเป็นสมมติฐานสำหรับ matcher ไม่ใช่หลักฐานเอกสารใน Graph RAG

หลังเปลี่ยนข้อมูลต้อง build/import และสร้าง GraphView ใหม่; แอปที่เปิดค้างต้อง restart/context reload เพื่ออ่านชุดใหม่
