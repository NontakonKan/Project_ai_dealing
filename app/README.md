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
| สเปกคณะ เช่น "ชอบผู้หญิงเรียนวิศวะ" | `chat` | กฎใน `pipelines/profile/faculty.py` (ไม่ใช้ LLM) → `preferences.faculty_wants` → คะแนนบวกตอนจับคู่ (`w_faculty` 0.3) ไม่ตัดคณะอื่นทิ้ง |
| ค่านิยม เช่น "ไม่ดื่มเหล้า อยากคบจริงจัง" | `chat` | LLM อ่าน 11 ด้าน: ลูก · ที่อยู่ · การเงิน · สัตว์เลี้ยง · เป้าหมายการคบ · เหล้า · บุหรี่ · เวลาส่วนตัว · โซเชียล · 🔒ศาสนา · 🔒อาหาร |
| "หาคู่ให้หน่อย" | `match` | Hybrid (Graph + Dense + ค่านิยม) → LLM อธิบาย → **Flex การ์ด** (ซีน 3) |
| กด "สนใจทำความรู้จัก" | `intro` | **ยินยอมทั้งสองฝ่าย:** ขอ LINE ID ของเรา (เก็บไว้ก่อน) → ส่งการ์ดของเราให้อีกฝ่ายประเมิน → ยินยอม = แลก LINE ID ทั้งคู่ / ไม่สะดวก = เราไม่ได้ข้อมูลใดๆ ของเขา และไม่แนะนำคู่นี้อีก |
| กด "ขอผ่านก่อน" | `match` | event pass (ไม่แนะนำซ้ำ) |
| กด "เลิกคุยกับคนนี้" แล้วบอกเหตุผล | `unmatch` | สกัดพฤติกรรม/รูปลักษณ์ → policy → อัปเดตโปรไฟล์ + รายงานอีกฝ่าย (เฉพาะพฤติกรรม) (ซีน 2) |
| คำถาม เช่น "แฟนเงียบใส่ควรทำไง" | `advice` | Routed Hybrid RAG จากความรู้ 10 แหล่ง + ชื่อแหล่งอ้างอิง |
| "โปรไฟล์ของฉัน" / "ลบข้อมูลของฉัน" | `account` | แสดงสิ่งที่ระบบจำ / ลบทุกอย่าง (PDPA) |

ผู้ใช้จริงจับคู่ได้ทั้งกับผู้ใช้จำลองและกับผู้ใช้จริงคนอื่นที่คุยกับ OA
`MOCK_USERS` ใน `app/.env` กำหนดผู้ใช้จำลองที่อยู่ใน pool: ตอนใช้งานจริงตั้งไว้ 6 คน (U031, U174 หญิง→ชาย · U050, U166 ชาย→หญิง · U172 หญิง→ทุกเพศ · U001 ชาย→ทุกเพศ) ใส่ `all` เพื่อใช้ทั้ง 300 คน

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

### รัน webhook บนเครื่องนี้ (Windows PowerShell)

หลัง `git pull origin main` ให้รันจาก root ของโปรเจกต์บนเครื่องที่จะรับ webhook:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt -r requirements-dense.txt
Copy-Item app\.env.example app\.env
```

ใส่ `LINE_CHANNEL_SECRET` และ `LINE_CHANNEL_ACCESS_TOKEN` ของ **Messaging API channel เดียวกัน** ใน `app/.env` บนเครื่องนี้ ห้ามส่งคีย์ผ่าน Git หรือใส่ในไฟล์ตัวอย่าง ถ้ามี API LLM ให้ตั้งค่า root `.env` บนเครื่องนี้แยกต่างหากตาม `pipelines/llm/README.md`; เครื่องที่ใช้ local LLM ต้องเปิด Ollama และมีโมเดลตาม config ด้วย

ฐาน ChromaDB ไม่อยู่ใน Git จึงต้องสร้างบนเครื่องนี้ครั้งแรก (ข้ามได้ถ้ามี index ที่สร้างไว้แล้ว):

```powershell
.\.venv\Scripts\python.exe -m pipelines.dense.run build
.\.venv\Scripts\python.exe -m app.check_line
.\.venv\Scripts\python.exe -m app.rich_menu
.\.venv\Scripts\python.exe -m app.rich_menu --publish
.\.venv\Scripts\python.exe -m uvicorn app.server:api --host 0.0.0.0 --port 8000
```

`app.check_line` ตรวจว่ามีค่าคีย์ทั้งสองและไฟล์ rich menu ครบ โดยไม่แสดงค่าคีย์หรือเรียก LINE API ส่วน `--publish` เป็นขั้นที่อัปโหลดภาพและตั้ง default rich menu จริง ให้รันเมื่อพร้อมใช้ channel แล้ว คำสั่ง `uvicorn` ต้องเปิดค้างไว้ จากอีกหน้าต่างให้เปิด HTTPS tunnel เช่น `ngrok http 8000` แล้วนำ URL ที่ได้ตามด้วย `/callback` ไปตั้งเป็น Webhook URL ใน LINE Developers Console เปิด Use webhook และกด Verify ตรวจ `http://localhost:8000/health` ว่า `line_configured` เป็น `true` จากนั้นลองกดทั้ง 4 ช่องบน LINE มือถือ

หากเปลี่ยน LINE channel ให้เปลี่ยนคีย์ทั้งคู่และ publish rich menu บน channel ใหม่อีกครั้ง คำสั่ง publish จะแสดง ID เมนูเดิมสำหรับ rollback; อย่าเก็บ access token ในภาพหน้าจอหรือ log ที่ส่งต่อ

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

## ดู log และผู้ใช้ในระบบ

terminal ที่รัน uvicorn จะแสดง 1 บรรทัดต่อ 1 event:
```
19:09:13 │ L0002 น้องมิ้น │ 💬 chat       │ "วันนี้ไปอ่านหนังสือ…" → จำได้: hobby:reading, trait:funny → ตอบ "…" │ 8.5s
19:09:36 │ L0002 น้องมิ้น │ 💞 find_match │ "หาคู่ให้หน่อย" → แนะนำ U027 (จำลอง) graph=0.27 dense=0.62 74% → [การ์ด] … │ 22.4s
19:10:02 │ L0001 Nont     │ 👆 postback   │ กดปุ่ม intro → L0002 → ส่งคำขอทำความรู้จัก … → 📨 push ถึง L0002 │ 1.2s
```
LINE ID ที่ผู้ใช้ส่งมาไม่ถูกแสดงใน log / ตั้ง `LOG_TEXT=0` ใน `app/.env` เพื่อซ่อนข้อความที่ผู้ใช้พิมพ์

อีกหน้าต่าง (ไม่ต้องหยุด bot):
```bash
.venv/bin/python -m app.admin users        # รายชื่อผู้ใช้จริง สถานะ ยินยอม จำนวนข้อความ
.venv/bin/python -m app.admin user L0002   # สิ่งที่ระบบจำ + ข้อความล่าสุดของคนนั้น
.venv/bin/python -m app.admin stats        # สรุป: เจตนา การ์ด events คำขอทำความรู้จัก
.venv/bin/python -m app.admin tail         # ข้อความใหม่แบบ realtime
```

## Error handling

| สถานการณ์ | การจัดการ |
|---|---|
| ลายเซ็นไม่ถูกต้อง | 401 ไม่ประมวลผล |
| ประมวลผลนาน | ตอบ LINE 200 ทันที แล้วทำงานเบื้องหลัง ถ้า replyToken หมดอายุ (~1 นาที) จะใช้ push แทน |
| LLM ตอบคุยเล่นล้มเหลว | ลองโมเดลสำรอง (Typhoon 3B) ถ้ายังไม่ได้ใช้ข้อความสำเร็จรูป |
| API (PSU AI) ล่ม / key ใช้ไม่ได้ | การ์ดอธิบายคู่สลับไปใช้ Typhoon 8B ในเครื่องอัตโนมัติ |
| LLM สกัดข้อมูลล้มเหลว | ข้ามการ merge รอบนั้น แต่ยังตอบผู้ใช้ได้ |
| exception อื่นๆ | log ลง stderr แล้วตอบ "ระบบขัดข้องชั่วคราว" (ไม่หลุดถึงผู้ใช้เป็น error) |
| โปรไฟล์ยังไม่พอจับคู่ | บอกผู้ใช้ว่าขาดอะไร |
| ความรู้ไม่พอตอบ | บอกว่าไม่มีข้อมูล + หัวข้อที่ตอบได้ ไม่แต่งเอง |

## ความเป็นส่วนตัว
- ขอความยินยอมก่อนใช้ข้อมูลจับคู่ / บล็อก OA = หลุดจาก pool ทันที
- สีผิวใช้ได้ต่อเมื่อยินยอมแยก (PDPA ม.26) / รูปลักษณ์ไม่อยู่ในข้อความที่ Dense embed
- **ศาสนา / อาหาร (ฮาลาล ฯลฯ)** เป็นข้อมูลอ่อนไหว: ถามความยินยอมแยกครั้งแรกที่ผู้ใช้พูดถึง ยินยอม = ใช้คำนวณคู่เท่านั้น / ไม่ยินยอม = ทิ้งและไม่ถามซ้ำ
  ไม่เก็บเป็นข้อความ (ไม่เข้า Dense, ไม่ส่งให้ LLM/API) ไม่แสดงบนการ์ด และไม่ log ค่า เห็นได้เฉพาะเจ้าของใน "โปรไฟล์ของฉัน" (🔒)
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
| `replies.py` | ตอบคุยเล่น (ผ่าน `providers`: Local หรือ `api:` + fallback) |
| `simulate.py` | จำลอง LINE ในเครื่อง + เดโม 3 ซีน / ทำความรู้จักแบบยินยอมทั้งสองฝ่าย |
| `log.py` | log 1 บรรทัดต่อ event ใน terminal ของ uvicorn |
| `admin.py` | ดูผู้ใช้ / สถิติ / ข้อความแบบ realtime |


## Conversation history และความจำระยะยาว

- `messages` เก็บประวัติต้นฉบับ ส่วน `conversation_memory` เก็บสรุปเป็นหัวข้อ พร้อมข้อความหลักฐานและ `source_id` จากผู้ใช้เท่านั้น คำตอบเก่าของบอตไม่ถูกสรุปเป็นข้อเท็จจริงของผู้ใช้
- `conversation_memory_revisions` เก็บการแก้ไข เมื่อผู้ใช้เปลี่ยนข้อมูล โมเดลเสนอการปรับ key เดิมและระบบตรวจว่าหลักฐานอยู่ในข้อความต้นทางก่อนบันทึก การอัปเดตกับ checkpoint อยู่ใน transaction เดียวกัน ถ้าโมเดลล้มเหลวหรือหลักฐานไม่ถูกต้องจะเก็บความจำเดิมไว้
- งานสรุปความจำและตอบคำถามย้อนใช้โมเดลในเครื่อง แม้ตั้งโมเดลงานอื่นเป็น API ส่วนความจำที่ผ่านตัวกรองอาจเข้า prompt RAG ตาม provider ของ RAG ตัวกรองข้อมูลส่วนตัวเป็นกฎเบื้องต้น ไม่ใช่ระบบตรวจข้อมูลส่วนตัวที่ครอบคลุมทุกภาษา/รูปแบบ
- ถามย้อน เช่น “ครั้งก่อนเล่าเรื่องค่าเช่าห้องว่าอะไร” จะค้นข้อความผู้ใช้ย้อนหลังด้วย character trigrams ที่รองรับข้อความไทย และอ่านคำตอบบอตในรอบนั้นด้วย โดยระบุชัดว่าคำตอบเก่าไม่ใช่หลักฐานความรู้ใหม่
- ขอบเขตปัจจุบัน: สรุปสูงสุด 12 ข้อความใหม่ล่าสุดต่อรอบ (รวมข้อความไม่เกิน 5,500 ตัวอักษร) และให้โมเดลเห็นสรุปเดิมล่าสุด 12 หัวข้อ ข้อความเก่าที่ยังไม่สรุปยังค้นได้ในประวัติ การค้นประวัติอ่านสูงสุด 1,000 ข้อความผู้ใช้ล่าสุดและเลือกข้อความที่เกี่ยวข้องภายในงบประมาณ 1,000 tokens สำหรับถามย้อน และ 400 tokens สำหรับเสริมคำถามต่อเนื่อง จึงไม่ใช่การรับประกันว่าจะจำหรือค้นพบทุกเรื่อง
- การ “ลืมหัวข้อ” เอาออกจากสรุปปัจจุบัน แต่ข้อความเดิมกับประวัติแก้ไขยังอยู่ การ “ลบข้อมูลของฉัน” ลบทั้งข้อความ สรุป ประวัติแก้ไข และ checkpoint
- ความจำนี้แยกจากโปรไฟล์ Matching: การแก้สรุปสนทนาไม่ได้แก้คะแนนหรือสเปกในโปรไฟล์โดยอัตโนมัติ
- ตารางใหม่สร้างอัตโนมัติเมื่อเปิด SQLite ไม่ต้องล้างฐานข้อมูลเดิม ทดสอบด้วย `.venv/bin/python -m unittest discover -s tests` จาก root

## Rich Menu

ภาพต้นฉบับอยู่ที่ `app/assets/rich_menu/menu-source.png`; ไฟล์ที่อัปโหลดคือ `menu.jpg`
แปลงเป็น JPEG 1520×1035 (ประมาณ 236 KB) โดยคงภาพและข้อความเดิม
ตาม [ข้อกำหนด LINE](https://developers.line.biz/en/reference/messaging-api/nojs/#upload-rich-menu-image)
แบ่งพื้นที่ซ้ายสามช่องเป็นโปรไฟล์ / ถามบอต / ลบข้อมูล และด้านขวาเป็นหาคู่
ปุ่มส่งข้อความเข้าระบบเดิม จึงยังเคารพขั้นตอน onboarding และสถานะที่ค้างอยู่
ปุ่มถามบอตในสถานะ ready ชวนให้พิมพ์คำถาม โดยไม่เรียกโมเดลหรือเพิ่มข้อความเมนูลงความจำ
ปุ่มลบข้อมูลเปิดข้อความยืนยันก่อน และลบจริงเมื่อกด “ยืนยันลบข้อมูล” เท่านั้น

ตรวจ JSON โดยไม่เรียก API:

```bash
.venv/bin/python -m app.rich_menu
```

ตั้ง `LINE_CHANNEL_ACCESS_TOKEN` ใน `app/.env` แล้วสร้าง/อัปโหลด/ตั้งเป็นเมนูเริ่มต้น:

```bash
.venv/bin/python -m app.rich_menu --publish
```

คำสั่งจะตรวจ definition กับ LINE ก่อน สร้างเมนูใหม่ อัปโหลดภาพ แล้วเปลี่ยน default
พร้อมตรวจ ID หลังเปลี่ยน ไม่ลบเมนูเดิม และพิมพ์ ID สำหรับย้อนกลับ
หากอัปโหลดล้มเหลว default เดิมยังอยู่ เมนูใหม่ที่สร้างค้างจะมี ID ใน output
การรัน publish ซ้ำสร้างเมนูใหม่ทุกครั้ง

```bash
.venv/bin/python -m app.rich_menu --restore richmenu-OLD_ID
```

รีสตาร์ตแอปหลังเปลี่ยนโค้ด handler แล้วทดสอบบน LINE มือถือ (Rich Menu ไม่แสดงบน LINE PC)
เมนูที่ผูกเฉพาะผู้ใช้มีลำดับความสำคัญเหนือ default จึงอาจยังเห็นเมนูเฉพาะผู้ใช้เดิม
