# pipelines — Data & Knowledge Base

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pipelines.mock.run   --n 300 --seed 42          # -> data/mock/
.venv/bin/python -m pipelines.ingest.run --chunk-size 300 --overlap 0.15   # -> data/processed/
```

| โฟลเดอร์ | ไฟล์ | หน้าที่ |
|---|---|---|
| `common/` | `paths.py` `io_utils.py` `taxonomy.py` | path กลาง, อ่าน/เขียน JSON, โหลด taxonomy |
| `mock/` | `config.py` | archetype, สัดส่วน, template ข้อความ |
| | `users.py` `summaries.py` | สร้างโปรไฟล์ + ข้อความสรุปสำหรับ embed |
| | `events.py` | unmatch/matched/pass + สะสม penalty (`apply_feedback`) |
| | `chats.py` | แชทจำลอง + gold extraction |
| | `compat.py` `ground_truth.py` | เฉลยการจับคู่ (oracle) สำหรับ Evaluation |
| | `report.py` `run.py` | สถิติ + CLI |
| `ingest/` | `sources.py` | ทะเบียนเอกสาร + กติกาเฉพาะไฟล์ (บทที่เก็บ, header ที่ทิ้ง) |
| | `extract.py` `ocr.py` | ดึงข้อความ PDF / OCR ไฟล์สแกน |
| | `clean.py` | แก้สระอำ, ลบ header/เลขหน้า/เลขอ้างอิง, ต่อบรรทัด |
| | `sectioner.py` | แบ่งตามบท/หัวข้อ + รวม section ที่สั้นเกิน |
| | `chunker.py` | recursive chunk ตามจำนวนคำ (PyThaiNLP) + overlap ระดับวลี |
| | `tagger.py` | ติด `concepts` / `topics` / `target_trait` ด้วย taxonomy id |
| | `report.py` `run.py` | สถิติคุณภาพ + before/after + CLI |
| `common/` | `validate_taxonomy.py` | ตรวจ taxonomy: id ซ้ำ, prefix, กฎอ้าง id ที่ไม่มี, alias ชนกัน (`python -m pipelines.common.validate_taxonomy`) |
| `feedback/` | `sensitive.py` | ตรวจคำรูปลักษณ์/สีผิว/สุขอนามัยด้วยคีย์เวิร์ด (ขอบคำ + บริบท กัน "ข้าวขาว") |
| | `policy.py` | กติกา: red flag -> ผู้พูด + รายงานอีกฝ่าย / รูปลักษณ์ -> ผู้พูดเท่านั้น / `appearance_score()` |
| | `apply.py` | อัปเดตโปรไฟล์ (noisy-OR สะสม, reported_traits >= 3) — ใช้ทั้ง mock และข้อมูลจริง |
| `profile/` | `normalize.py` | คำอิสระ -> รหัส taxonomy: exact -> contains -> bge-m3 embedding -> unmapped_terms.jsonl |
| `mock/` | `appearance.py` | รูปลักษณ์จริง (ซ่อน) / ที่เจ้าตัวระบุ / สเปกรูปลักษณ์ |
| `retrieval/` | `contract.py` | สัญญากลาง `RetrievalResult` ที่ Dense/Graph/Hybrid ต้องคืน |
| | `stubs/` | retriever ชั่วคราวให้ส่วน LLM ทดสอบได้ก่อน |
| `llm/` | ดู [llm/README.md](llm/README.md) | Local LLM: extraction + RAG answer + benchmark |

เพิ่มเอกสารใหม่: เพิ่ม entry ใน `ingest/sources.py` อย่างเดียว ไม่ต้องแก้ logic
