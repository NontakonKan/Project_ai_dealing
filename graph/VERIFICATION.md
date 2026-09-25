# ผลตรวจ Graph

ตรวจบนข้อมูลใน repository วันที่ 26 กันยายน 2026 (เวลาไทย)

## ผลที่สร้างและอ่านกลับจาก Neo4j

| รายการ | ผล |
|---|---:|
| Nodes | 406 |
| Relationships | 6,619 |
| Users | 300 |
| Taxonomy concepts | 61 |
| Sources ที่มีข้อความพร้อมแล้ว | 1 |
| BookChunks | 44 |
| Compatibility rules | 14 |
| REPORTED_AS ที่ผ่านเกณฑ์ | 17 |

Snapshot: `22515caa90bb706f8fa8871d5a9c66315edca3a833b9a2b500721063b6fc6037`

นำเข้าผ่าน Python driver 5.28.6 ไปยัง **Neo4j Community 5.26.0 จริง** ใน instance ทดลองแยกที่ `/tmp/psu-graph-runtime` ใช้ Java 21 และ localhost ports 17474/17687 เพราะ Docker daemon ของเครื่องไม่ได้เปิดอยู่ ตรวจ syntax ของ compose ด้วย `docker compose ... config --quiet` ผ่าน แต่ไม่ได้อ้างว่าทดสอบการเปิด container สำเร็จ

## การทดสอบที่ผ่าน

`GRAPH_NEO4J_TEST=1 .venv/bin/python -m unittest discover -s graph/tests -v`

**13 tests ผ่าน ไม่มี skip ในรอบที่เชื่อมต่อ Neo4j**:

- 10 tests สำหรับข้อมูล: input coverage, deterministic output, กัน oracle/extra fields, consent, usable reports, source text/pages, parallel events, duplicate events, schema/endpoints, content hash
- 3 tests กับฐานข้อมูลจริง: นำเข้าซ้ำและรัน query ทุกตัว, เปลี่ยน snapshot แล้วไม่พบรายงานเก่า/consent เก่า, ไม่มีการสร้างหลักฐานให้แนวคิดที่ไม่มี chunk

ทั้ง 7 blocks ใน `queries.cypher` รันกับ Neo4j ได้ ผลลัพธ์ตามลำดับ: 21, 14, 100, 30, 3, 406 และ 6,619 rows โดยสองคำสั่งท้ายใช้ export โหนดและความสัมพันธ์ทั้งหมดของ active snapshot (ตัวอย่างก่อนหน้าบางอันตั้ง LIMIT ไว้)

ขั้นตอนใช้งานปัจจุบันอ่านจาก `data/` แล้วนำเข้า Neo4j โดยตรง ไม่มีไฟล์กราฟตัวกลางหรือหน้า HTML ที่สร้างเอง การดูกราฟและ export ใช้ Neo4j Browser ตามคำสั่งใน `queries.cypher`

## ขอบเขตของผลตรวจ

ผลนี้ยืนยันการสร้างและใช้งานกราฟตามข้อมูลที่มี ไม่ได้วัดความแม่นยำการจับคู่ ไม่ได้พิสูจน์กฎทางจิตวิทยา และไม่ได้ทดสอบ RAG/LLM

กราฟยังมีข้อมูลจากเอกสารเพียงแหล่งเดียวตาม chunks ปัจจุบัน ข้อจำกัดและรายการแนวคิดที่ไม่มี chunks ดูจาก `python3 -m graph.build` ผลในเอกสารนี้เป็นของ snapshot ที่ระบุ เมื่อเปลี่ยนข้อมูลให้ build/import และทดสอบใหม่
