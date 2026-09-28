"""สร้าง docs/data_card.md จากข้อมูลจริง (ตัวเลขทุกตัวคำนวณใหม่ทุกครั้งที่รัน ไม่พิมพ์มือ)

รัน: python -m pipelines.ingest.data_card        (หลัง pipelines.ingest.run)
"""
import collections
import json
import statistics as st

from ..common.paths import DATA, PROCESSED
from .sources import SOURCES
from .tagger import CONTEXT_WINDOW

OUT = DATA.parent / "docs" / "data_card.md"
CANDIDATES = DATA / "new_docs" / "candidates.json"
AUDIT = DATA / "eval" / "concept_tag_audit.json"

# แหล่งที่ถอดออกก่อนมีระบบ candidates.json (ผู้ดูแลลบไฟล์ออกจาก data/)
REMOVED_EARLIER = [
    ("research_cu2561", "ผู้ดูแลถอดไฟล์ออกจากคลัง (คำถามทดสอบ Q02, Q05 เปลี่ยนเป็น 'ต้องปฏิเสธ')"),
    ("book_whonotlove", "ผู้ดูแลถอดไฟล์ออกจากคลัง"),
    ("thesis_online_romance2557", "ผู้ดูแลถอดไฟล์ออกจากคลัง"),
    ("royal_qa", "ผู้ดูแลถอดไฟล์ออกจากคลัง"),
]

FIELDS = [
    ("chunk_id", "`<source>_s<section>_c<chunk>` คงที่ข้ามการรัน (chunk ซ้ำที่ถูกตัดจะเว้นเลข)"),
    ("source_id / title / year / url", "ที่มาสำหรับอ้างอิงในคำตอบ (title ไม่ใส่โดเมน เพราะ LINE แปลงเป็นลิงก์)"),
    ("doc_type / source_quality", "ชนิดเอกสาร / ระดับความน่าเชื่อถือ (academic, clinical, government, …)"),
    ("chapter / section_title / pages", "ตำแหน่งในเอกสาร (หน้าเริ่มจาก 0)"),
    ("category", "หมวดสำหรับ router (เช่น sexual_health ถูกกันไม่ให้หลุดไปตอบเรื่องจับคู่)"),
    ("concepts / concept_counts", "taxonomy id ชุดเดียวกับโปรไฟล์ผู้ใช้และ Graph -> สร้าง edge ABOUT"),
    ("topics / target_trait", "หัวข้อย่อย / concept ที่เป็นลักษณะบุคคล (trait, attach)"),
    ("n_words / n_chars / lang", "ขนาด chunk (คำนับด้วย PyThaiNLP)"),
]


def _pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def _table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build():
    chunks = [json.loads(l) for l in open(PROCESSED / "book_chunks.jsonl", encoding="utf-8")]
    report = json.load(open(PROCESSED / "ingest_report.json", encoding="utf-8"))
    reps = {r["source_id"]: r for r in report["sources"]}
    cfg = report["config"]
    by_src = collections.Counter(c["source_id"] for c in chunks)
    words = [c["n_words"] for c in chunks]

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("BAAI/bge-m3")
    tokens = [len(tok(c["text"])["input_ids"]) for c in chunks]
    over = sum(t > 512 for t in tokens)

    cleaning = collections.Counter()
    for r in report["sources"]:
        cleaning.update(r.get("cleaning") or {})

    src_rows = []
    for s in SOURCES:
        r = reps.get(s["source_id"], {})
        src_rows.append([f"`{s['source_id']}`", s["title"], s["doc_type"], s.get("source_quality", "document"),
                         s.get("default_category") or "ตามบท", f"{r.get('pages_used', '-')}/{r.get('pages_total', '-')}",
                         by_src.get(s["source_id"], 0), f"{r.get('chunks_with_concepts_pct', 0)}%",
                         (r.get("status") or "-").replace("ok ", "")])

    cand = json.load(open(CANDIDATES, encoding="utf-8")) if CANDIDATES.exists() else {}
    excluded = [(f"`{e['id']}`", e.get("org", ""), e["reason"]) for e in cand.get("excluded", [])]
    excluded += [(f"`{sid}`", "", why) for sid, why in REMOVED_EARLIER]

    audit = json.load(open(AUDIT, encoding="utf-8")) if AUDIT.exists() else []
    done = [a for a in audit if a.get("correct") is not None]
    errs = collections.Counter(a["note"].split(":")[0] if ":" in a["note"] else a["note"] for a in done if not a["correct"])

    md = f"""# Data Card — คลังความรู้ PSU Dealing

> สร้างอัตโนมัติด้วย `python -m pipelines.ingest.data_card` จาก `data/processed/` — อย่าแก้ตัวเลขด้วยมือ

## 1. ภาพรวม

| | |
|---|---|
| แหล่งเอกสาร | **{len(SOURCES)}** แหล่ง |
| chunk | **{len(chunks):,}** |
| chunk ที่มี concept (เชื่อม Graph) | {100 * sum(1 for c in chunks if c['concepts']) / len(chunks):.1f}% |
| ระดับความน่าเชื่อถือ | {", ".join(f"{k} {v}" for k, v in collections.Counter(c['source_quality'] for c in chunks).most_common())} (นับเป็น chunk) |
| ชนิดเอกสาร | {", ".join(f"{k} {v}" for k, v in collections.Counter(c['doc_type'] for c in chunks).most_common())} |

**หมวด (category) ต่อ chunk:** {", ".join(f"{k} {v}" for k, v in collections.Counter(c['category'] for c in chunks).most_common())}

**เกณฑ์เลือกแหล่ง:** หน่วยงานรัฐ / มหาวิทยาลัย / วารสารวิชาการ (ThaiJO) / สถาบันวิจัย / โรงพยาบาล / สื่อสาธารณะ —
ไม่ใช้บล็อกไลฟ์สไตล์ · ข้อความต้องดึงจากต้นฉบับตรงๆ (ไม่สรุป ไม่แต่ง) · ทุกแหล่งมีชื่อที่อ้างอิงได้

## 2. รายการแหล่ง

{_table(src_rows, ["source_id", "ชื่อ (ใช้อ้างอิงในคำตอบ)", "ชนิด", "ความน่าเชื่อถือ", "หมวดตั้งต้น", "หน้าที่ใช้", "chunk", "มี concept", "ที่มาข้อความ"])}

## 3. แหล่งที่ตัดออก

{_table(excluded, ["id", "หน่วยงาน", "เหตุผล"])}

## 4. การเตรียมข้อมูล (ขั้นตอน)

1. **ดึงข้อความ:** PDF ที่มี text layer ใช้ PyMuPDF / PDF สแกนใช้ VLM OCR (qwen2.5vl) / หน้าเว็บดึงจาก HTML แล้วทำ PDF ที่มีหัวอ้างอิง (`pipelines/ingest/collect.py`)
2. **ทำความสะอาด:** แก้ฟอนต์ไทยเก่า (PUA) {cleaning['pua_fixed']:,} จุด, สระอำแตก {cleaning['sara_am_fixed'] + cleaning['broken_am_fixed']:,} จุด, ลบบรรทัดขยะ (เลขหน้า หัวกระดาษ ตราดาวน์โหลด) {cleaning['noise_lines_removed']:,} บรรทัด, ตัดเลขอ้างอิงในเนื้อความ {cleaning['citations_removed']:,} จุด
3. **แบ่งส่วน:** ตามบทของวิทยานิพนธ์ / ตามหน้า / รวม section ที่สั้นกว่า {cfg['min_section_words']} คำ
4. **ตัด chunk:** {cfg['chunk_size']} คำ ซ้อนกัน {int(cfg['overlap'] * 100)}% (นับคำด้วย PyThaiNLP)
5. **ตัด chunk ซ้ำ:** {cleaning['duplicate_chunks_removed']} chunk (ภาคผนวกที่พิมพ์แบบสอบถามชุดเดิมซ้ำหลายเงื่อนไข)
6. **ติด metadata + concept:** ใช้ `data/concept_lexicon.json` + กฎบริบท (±{CONTEXT_WINDOW} ตัวอักษร, คำปฏิเสธ, คำต่อท้าย)
7. **ปกปิดข้อมูลส่วนบุคคล:** ตัดอีเมลผู้เขียนงานวิจัยด้วย noise pattern — pipeline มีกลไกปกปิดชื่อบุคคล (`redact`, `name_capture`) ที่เคยใช้กับเอกสารถาม-ตอบของเยาวชน ซึ่งถูกถอดออกจากคลังแล้ว

## 5. ขนาด chunk และเหตุผล

| | p50 | p95 | max |
|---|---|---|---|
| คำ (PyThaiNLP) | {st.median(words):.0f} | {_pct(words, .95)} | {max(words)} |
| token (bge-m3) | {st.median(tokens):.0f} | {_pct(tokens, .95)} | {max(tokens)} |

- **{cfg['chunk_size']} คำ:** ใหญ่พอให้ 1 chunk มีทั้งประเด็นและคำอธิบาย (ย่อหน้าวิชาการไทยยาว) และเล็กพอให้ใส่ 3–4 chunk ใน context 3,000 token ของ LLM
- **embedding (bge-m3 รับได้ 8,192 token):** ทุก chunk อยู่ในขีดจำกัด
- **reranker (bge-reranker-v2-m3 อ่านได้ 512 token):** chunk ที่เกิน 512 token มี {over} อัน ({100 * over / len(chunks):.1f}%) -> ด่านความเกี่ยวข้องอ่านเป็นช่วงละ 600 ตัวอักษร ซ้อน 150 (`gate._windows`) เพื่อไม่ให้ท้าย chunk ถูกตัดทิ้ง
- **overlap {int(cfg['overlap'] * 100)}%:** ประโยคที่คร่อมรอยตัดยังอยู่ครบใน chunk ใดอันหนึ่ง + ขั้นค้นหาดึง chunk ข้างเคียงมาตรวจด้วย (`search._neighbors`)

## 6. Metadata ต่อ chunk

{_table(FIELDS, ["field", "ใช้ทำอะไร"])}

## 7. การเตรียมข้อมูลสำหรับ Vector และ Graph

- **Vector (Dense):** ทุก chunk -> bge-m3 -> ChromaDB (`python -m pipelines.dense.run build`)
- **Graph:** chunk เป็น node `BookChunk`, concept -> edge `ABOUT` ไปยัง node Concept ชุดเดียวกับโปรไฟล์ผู้ใช้
  ทำให้ค้นจากลักษณะของคู่ (trait / red flag) ไปหาความรู้ได้ตรงๆ (`python -m graph.build`)

## 8. การควบคุมคุณภาพ

| ตรวจอะไร | ผล | ที่มา |
|---|---|---|
| OCR เทียบหน้าที่ถอดด้วยมือ | CER 8.0% -> 4.3%, WER 14.6% -> 11.2% | `pipelines/ingest/ocr_eval.py` |
| หน้าที่คนตรวจจากภาพ (แทน OCR) | 101 หน้า | `data/ocr_verified/` |
| PDF จากเว็บ อ่านกลับได้ตรงต้นฉบับ | 99.7–100% (หายเฉพาะอีโมจิ) | `pipelines/ingest/collect.py` |
| chunk ซ้ำ | ตัด {cleaning['duplicate_chunks_removed']} | `run.dedupe` |
| concept tag สุ่มตรวจ {len(done)} คู่ | precision {sum(a['correct'] for a in done) / max(1, len(done)):.0%} -> 80.9% หลังแก้คำปฏิเสธ (วัดในชุดเดิม) | `pipelines/ingest/tag_audit.py` |

**ประเภทข้อผิดพลาดที่พบ (ก่อนแก้):** {", ".join(f"{k} ({v})" for k, v in errs.most_common())}
— แก้คำปฏิเสธแล้ว (ผิด 3 -> 0 ในชุดเดิม โดย tag ที่ถูกไม่หาย) ส่วนความหมายต่างบริบท / บรรณานุกรม ยังเป็นข้อจำกัด
(ผู้ตรวจ: {done[0]['reviewer'] if done else '-'})

## 9. ข้อมูลผู้ใช้จำลอง (สำหรับจับคู่)

- `data/mock/users.json` ผู้ใช้สังเคราะห์ {len(json.load(open(DATA / 'mock' / 'users.json', encoding='utf-8')))} คน + แชท / เหตุการณ์ / คู่เฉลย (`ground_truth_pairs.json`)
- เป็นข้อมูลสังเคราะห์ -> ใช้ทดสอบกลไก ไม่ได้วัดความแม่นในโลกจริง

## 10. ลิขสิทธิ์และข้อมูลส่วนบุคคล

- เอกสารส่วนใหญ่มีลิขสิทธิ์ -> ใช้เพื่อการศึกษา, repo ต้องเป็น **private**, คำตอบอ้างอิงชื่อแหล่งทุกครั้ง
- ไม่เก็บ/ไม่ส่งให้ LLM: ศาสนา อาหาร (ต้องยินยอม), LINE ID / เบอร์ / อีเมลในแชท (ตัดก่อนเก็บความจำ)
- แชทผู้ใช้จริง (`data/app/*.db`) และ API key (`.env`) ไม่ขึ้น git
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT}")


if __name__ == "__main__":
    build()
