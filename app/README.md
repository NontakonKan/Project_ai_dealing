# ส่วน 7: System Integration (LINE OA)

```
LINE ──POST /callback──► server.py ──ตรวจลายเซ็น (HMAC-SHA256)──► 200 ทันที
                                        │ BackgroundTasks
                                        ▼
                                  handlers.dispatch(event)
             follow/unfollow │ postback (ปุ่ม) │ message ──► intent.classify
                                        ▼
  flows/  onboarding · chat · match · advice · unmatch · account
            │           │        │        │          │
            │   llm.extract_profile   hybrid.matcher  llm.extract_unmatch
            │   hybrid.values_extract llm.explain_match feedback.policy/apply
            │   replies.chat_reply    RoutedKnowledge + llm.rag_answer
            ▼
  profile.py (merge / decay / เพดานขนาด / summaries) ─► storage.py (SQLite) ─► live.py (เข้า pool Dense+Graph+Hybrid)
                                        ▼
                         line_api.reply (หรือ push ถ้า replyToken หมดเวลา)
```

## ผู้ใช้คุยอะไรได้

| สิ่งที่พิมพ์ / กด | flow | เบื้องหลัง |
|---|---|---|
| เพิ่มเพื่อน OA | `onboarding` | ขอความยินยอม → เพศ → เพศที่สนใจ → อายุ → คณะ |
| เล่าชีวิตประจำวัน/สเปก เช่น "ชอบทำอาหาร ชอบคนใจเย็น" | `chat` | สกัดบุคลิก + ค่านิยม → merge โปรไฟล์ → ตอบแบบเพื่อน (ซีน 1) |
| "หาคู่ให้หน่อย" | `match` | Hybrid (Graph + Dense + ค่านิยม) → LLM อธิบาย → **Flex การ์ด** (ซีน 3) |
| กด "สนใจทำความรู้จัก" | `intro` | **ยินยอมทั้งสองฝ่าย:** ขอ LINE ID ของเรา (เก็บไว้ก่อน) → ส่งการ์ดของเราให้อีกฝ่ายประเมิน → ยินยอม = แลก LINE ID ทั้งคู่ / ไม่สะดวก = เราไม่ได้ข้อมูลใดๆ ของเขา และไม่แนะนำคู่นี้อีก |
| กด "ขอผ่านก่อน" | `match` | event pass (ไม่แนะนำซ้ำ) |
| กด "เลิกคุยกับคนนี้" แล้วบอกเหตุผล | `unmatch` | สกัดพฤติกรรม/รูปลักษณ์ → policy → อัปเดตโปรไฟล์ + รายงานอีกฝ่าย (เฉพาะพฤติกรรม) (ซีน 2) |
| คำถาม เช่น "แฟนเงียบใส่ควรทำไง" | `advice` | Routed Hybrid RAG จากความรู้ 10 แหล่ง + ชื่อแหล่งอ้างอิง |
| "โปรไฟล์ของฉัน" / "ลบข้อมูลของฉัน" | `account` | แสดงสิ่งที่ระบบจำ / ลบทุกอย่าง (PDPA) |

ผู้ใช้จริงจับคู่ได้ทั้งกับผู้ใช้จำลอง 300 คน และกับผู้ใช้จริงคนอื่นที่คุยกับ OA

## ทดสอบในเครื่อง (ไม่ต้องมี token)

```bash
.venv/bin/pip install -r requirements-app.txt -r requirements-dense.txt
.venv/bin/python -m pipelines.dense.run build              # ครั้งแรก
.venv/bin/python -m app.simulate --demo                    # เดโม 3 ซีนจาก req.md
.venv/bin/python -m app.simulate --mutual                  # เดโมทำความรู้จักแบบยินยอมทั้งสองฝ่าย (ผู้ใช้ A/B/C)
.venv/bin/python -m app.simulate                           # พิมพ์คุยเอง (#1 #2 = กดปุ่ม, /as B = สลับผู้ใช้, /q = ออก)
.venv/bin/python -m unittest discover -s tests
```
simulator ใช้ฐานข้อมูลแยก `data/app/simulate.db` ต้องเปิด Ollama ไว้

## ต่อ LINE จริง

1. [LINE Developers Console](https://developers.line.biz/console/) → สร้าง Provider → **Messaging API channel**
2. แท็บ Basic settings: คัดลอก **Channel secret** / แท็บ Messaging API: กด Issue **Channel access token (long-lived)**
3. สร้างไฟล์ `app/.env` (ไม่ขึ้น git):
   ```
   LINE_CHANNEL_SECRET=xxxxxxxx
   LINE_CHANNEL_ACCESS_TOKEN=xxxxxxxx
   ```
4. รัน server และเปิดทางให้เข้าถึงจากภายนอก:
   ```bash
   .venv/bin/uvicorn app.server:api --host 0.0.0.0 --port 8000
   ngrok http 8000            # อีกหน้าต่าง -> ได้ https://xxxx.ngrok-free.app
   ```
5. Console → Messaging API → **Webhook URL** = `https://xxxx.ngrok-free.app/callback` → กด Verify → เปิด **Use webhook**
6. LINE Official Account Manager → Response settings: **ปิด Auto-reply** และ **Greeting message** (บอทตอบเอง)
7. สแกน QR ของ OA เพื่อเพิ่มเพื่อน → เริ่มคุยได้เลย ตรวจสถานะได้ที่ `http://localhost:8000/health`

## Error handling

| สถานการณ์ | การจัดการ |
|---|---|
| ลายเซ็นไม่ถูกต้อง | 401 ไม่ประมวลผล |
| ประมวลผลนาน | ตอบ LINE 200 ทันที แล้วทำงานเบื้องหลัง ถ้า replyToken หมดอายุ (~1 นาที) จะใช้ push แทน |
| LLM ตอบคุยเล่นล้มเหลว | ลองโมเดลสำรอง (Typhoon 3B) ถ้ายังไม่ได้ใช้ข้อความสำเร็จรูป |
| LLM สกัดข้อมูลล้มเหลว | ข้ามการ merge รอบนั้น แต่ยังตอบผู้ใช้ได้ |
| exception อื่นๆ | log ลง stderr แล้วตอบ "ระบบขัดข้องชั่วคราว" (ไม่หลุดถึงผู้ใช้เป็น error) |
| โปรไฟล์ยังไม่พอจับคู่ | บอกผู้ใช้ว่าขาดอะไร |
| ความรู้ไม่พอตอบ | บอกว่าไม่มีข้อมูล + หัวข้อที่ตอบได้ ไม่แต่งเอง |

## ความเป็นส่วนตัว
- ขอความยินยอมก่อนใช้ข้อมูลจับคู่ / บล็อก OA = หลุดจาก pool ทันที
- สีผิวใช้ได้ต่อเมื่อยินยอมแยก (PDPA ม.26) / รูปลักษณ์ไม่อยู่ในข้อความที่ Dense embed
- เหตุผลเลิกคุย: อีกฝ่ายไม่เห็น และถูกนับรายงานเฉพาะพฤติกรรม (ใช้ได้เมื่อ ≥ 3 คน) / การ์ดไม่เปิดเผยว่าใครถูกรายงาน
- ผู้ใช้ดูสิ่งที่ระบบจำ และลบข้อมูลทั้งหมดได้เอง
- **LINE ID ส่งต่อเฉพาะเมื่อยินยอมทั้งสองฝ่าย** (LINE API ไม่ให้ bot เห็น ID ของผู้ใช้ จึงขอให้ผู้ใช้ส่งเอง เก็บแยกในตาราง `contacts`) การ์ดคำขอไม่มีช่องทางติดต่อ
- ข้อความ push (แจ้งคำขอ / ผลการตอบรับ) นับโควตาของ OA

## ไฟล์
| ไฟล์ | หน้าที่ |
|---|---|
| `config.py` | env / `app/.env`, โมเดล, เพดาน, decay |
| `server.py` | FastAPI `/callback` (ตรวจลายเซ็น) + `/health` |
| `line_api.py` | ตรวจลายเซ็น, reply / push / get_profile (โหมดจำลองเมื่อไม่มี token) |
| `handlers.py` | รับ event → เลือก flow + error handling |
| `intent.py` | แยกเจตนาข้อความด้วยกฎ |
| `flows/` | onboarding · chat · match · **intro** (ยินยอมทั้งสองฝ่าย) · advice · unmatch · account |
| `profile.py` | โปรไฟล์ผู้ใช้จริง: merge, decay, เพดาน, summaries, describe |
| `live.py` | เอาผู้ใช้จริงเข้า Hybrid context (Graph add, Dense สด, ค่านิยม, รายงาน) |
| `storage.py` | SQLite: ผู้ใช้ ข้อความ โปรไฟล์ events คำแนะนำ รายงาน |
| `flex.py` | ข้อความ / quick reply / Flex การ์ด |
| `replies.py` | ตอบคุยเล่นด้วย Local LLM + fallback |
| `simulate.py` | จำลอง LINE ในเครื่อง + เดโม 3 ซีน |
