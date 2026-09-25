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

เพิ่มเอกสารใหม่: เพิ่ม entry ใน `ingest/sources.py` อย่างเดียว ไม่ต้องแก้ logic
