# ตรวจความพร้อมระบบ 2026-09-28

> ผลประเมินนี้เป็น baseline ก่อน merge `main` ที่ตัด chunk ซ้ำ 18 รายการ ปัจจุบันคลังเหลือ 1,035 chunks และต้องสร้าง ChromaDB/วัด retrieval ใหม่ก่อนอ้างเป็นผลปัจจุบัน

ตรวจจาก branch `faculty_score` หลัง merge commit `6928331` บนเครื่อง Windows เครื่องนี้ ผลด้านล่างเป็นการทดลองกับผู้ใช้จำลองและชุดคำถามใน repo ไม่ใช่คะแนนจากผู้ใช้จริงหรือการทดสอบ LINE production

## สิ่งที่ทำและตรวจได้

- สร้าง ChromaDB ใหม่จาก `data/processed/book_chunks.jsonl` โดยใช้ `BAAI/bge-m3`: persona 288, preference 288, avoid 232, knowledge **1,053** รายการ ตรวจ manifest แล้วสลับเป็น `data/chroma_db/` ฐานเก่า 129 รายการสำรองไว้ใน workspace ของ Codex (นอก repo)
- ค้นตัวอย่างภาษาไทยเรื่องการเริ่มคุยกับคนที่สนใจ พบเอกสาร `thesis_start_romance2549` ที่เกี่ยวข้อง
- `python -m unittest discover -s tests -v`: 34 tests ผ่าน; `python -m unittest discover -s graph/tests -v`: 12 ผ่าน 3 ข้ามเพราะต้องเปิด Neo4j จริง
- API key rotation และ fallback ผ่าน unit tests แต่รอบนี้ไม่ได้ทดสอบ LINE webhook, Ollama จริง หรือการหักเครดิต API จริง

## ผลจับคู่ (288 โปรไฟล์ที่มีเฉลย)

ตัวชี้วัดคำนวณจาก `data/mock/ground_truth_pairs.json`; P@5 สูงดีกว่า, Violation@5 ต่ำดีกว่า การเปรียบเทียบใช้ candidate ชุดเดียวกัน ผลฉบับเต็มอยู่ที่ `data/eval/dense_1053_20260928.json`, `data/eval/hybrid_1053_full_20260928.json` และ `data/eval/match_app_config_1053_20260928.json`

| วิธี | P@5 | MRR | Violation@5 |
|---|---:|---:|---:|
| Dense (negative penalty 0.15) | 0.1132 | 0.2613 | 0.1250 |
| Graph | 0.2611 | 0.5469 | 0.1278 |
| Hybrid RRF พื้นฐาน | 0.2014 | 0.4248 | 0.1257 |
| Hybrid weighted, Dense 0.3 | 0.2465 | 0.5297 | 0.1264 |
| **Hybrid ที่ LINE app ใช้จริง** (weighted 0.3 + ค่านิยมแบบโครงสร้าง + คณะ) | **0.3201** | **0.6383** | 0.1278 |

ข้อสรุป: Hybrid RRF พื้นฐานด้อยกว่า Graph เดี่ยวในชุดนี้ แต่ config ที่แอปใช้จริงเหนือกว่า Graph ใน P@5 และ MRR ความต่างนี้มาจากการเพิ่มสัญญาณค่านิยมและคณะที่ผู้ใช้ระบุ จึงไม่ควรกล่าวว่า fusion อย่างเดียวทำให้ดีขึ้น ค่า Violation@5 ยังอยู่ราว 0.12–0.13 ทุกวิธี: `must_exclude` ในเฉลยรวม red flag ที่ข้อมูลใช้งานจริงอาจยังไม่ครบเงื่อนไขรายงาน 3 ครั้ง จึงต้องตรวจรายกรณีก่อนตีความว่าเป็นการฝ่าฝืน hard filter

## ผลค้นความรู้ (41 ข้อมีคำตอบ, 11 ข้อไม่มีคำตอบ)

วัด Hit@5 จาก expected keywords อย่างน้อยครึ่งหนึ่งในชุด `data/eval/rag_questions.json` จึงเป็น proxy ของความเกี่ยวข้อง ไม่ใช่การตรวจความถูกต้องของคำตอบโดยคน ผลอยู่ที่ `data/eval/knowledge_1053_no_rerank_20260928.json` และ **ยังไม่รวม cross-encoder rerank, relevance gate หรือ LLM**

| วิธี | Hit@5 | MRR@5 | ว่างเมื่อไม่มีคำตอบ | เวลาเฉลี่ยต่อคำถาม |
|---|---:|---:|---:|---:|
| Dense | 0.854 | 0.733 | 0/11 | 811 ms |
| Graph | 0.122 | 0.090 | 10/11 | 4,045 ms |
| Hybrid RRF | 0.902 | 0.750 | 0/11 | 4,160 ms |
| Routed | 0.902 | 0.780 | 0/11 | 8,918 ms |

Hybrid เพิ่ม Hit@5 จาก Dense 0.854 เป็น 0.902 และ Routed เพิ่ม MRR@5 เป็น 0.780 แต่มีต้นทุนเวลาเพิ่มขึ้นชัดเจน ส่วน `empty_on_unanswerable` ที่ 0/11 สำหรับ Dense/Hybrid/Routed แสดงว่าการค้นอย่างเดียวไม่พอจะปฏิเสธคำถามนอกคลัง ต้องพึ่ง relevance gate และการตรวจคำตอบหลัง LLM ซึ่งยังต้องวัดร่วมกันใหม่ การรัน cross-encoder เต็มชุดบน CPU ใช้เวลาสูงมาก จึงไม่ได้ใส่ตัวเลขแทนผลจริง

## ประเมินตาม rubric (ชั่วคราว)

| ด้าน | ระดับที่มีหลักฐานรองรับตอนนี้ | สิ่งที่ยังขาดก่อนอ้าง Level 5 |
|---|---|---|
| Data / Knowledge Base | Level 4 | Data card, ตรวจ concept tags โดยคน, สรุปลิขสิทธิ์/PII |
| Dense RAG | Level 4 | ตาราง Top-K/threshold/rerank และผลของ LLM บนคลังใหม่ |
| Graph RAG | Level 3–4 | ทดสอบ Neo4j สด, ผูกกฎ taxonomy กับหลักฐาน, ตัวอย่างที่ Graph ช่วยจริง |
| Hybrid RAG | Level 4 สำหรับจับคู่; Level 3–4 สำหรับคำปรึกษา | ablation router/gate/rerank/LLM และทดสอบคำตอบสุดท้าย |
| Local + API LLM | Level 3–4 | วัด fallback จริง, เวลา/token/ทรัพยากร/ค่าใช้จ่ายบนงานเดียวกัน |
| Integration | Level 3 | LINE end-to-end และ error-path test; เครื่องนี้ไม่มี LINE channel credentials และ Ollama ที่เปิดใช้งาน |
| Evaluation | Level 4 สำหรับ retrieval; Level 3 สำหรับระบบรวม | gold set คนตรวจ, รันซ้ำ 3 รอบ, red-team, วิเคราะห์ข้อผิดพลาด |
| Documentation | Level 3–4 | คู่มือ Windows/เครื่องขั้นต่ำ, แผนภาพสถาปัตยกรรม, demo script และผลทดสอบจริง |

**ภาพรวม: ยังไม่ควรอ้างว่า Level 5 หรือพร้อมใช้งาน production** มีองค์ประกอบหลักและผลทดลอง retrieval ที่วัดซ้ำได้ แต่ยังไม่มีการยืนยัน LINE → retrieval → LLM → คำตอบบนเครื่องนี้ และยังไม่มีการตรวจคุณภาพคำตอบโดยคนกับคลังล่าสุด ระดับโดยรวมที่ปลอดภัยในการนำเสนอขณะนี้คือ **Level 3–4 (provisional)** ขึ้นกับผลทดสอบระบบจริงที่ยังขาด

## งานที่ต้องทำต่อก่อนส่ง

1. เปิด Ollama/Neo4j และตั้ง LINE channel ในสภาพแวดล้อมทดสอบ แล้วรัน smoke test ผ่าน webhook จริงพร้อม error-path
2. วัด gated + reranked RAG และคุณภาพคำตอบ LLM บน 52 คำถามชุดเดียวกัน; ตรวจคำตอบ 20–30 ข้อโดยคนและรันซ้ำ 3 รอบ
3. ทำ red-team เรื่อง prompt injection, คำถามกึ่งเกี่ยว และการขอข้อมูลผู้ใช้คนอื่น
4. เพิ่มตาราง latency p50/p95, token และค่าใช้จ่ายจริงของ API; วัด RAM/VRAM ของ Local
5. ตรวจ `must_exclude` ที่ยังถูกแนะนำทีละกรณี และเขียนนโยบายว่ากรณีใดต้องตัดออกแน่นอน
