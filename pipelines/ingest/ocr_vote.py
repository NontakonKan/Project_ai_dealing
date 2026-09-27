"""รวมผล OCR หลายรอบด้วยการโหวตรายคำ — แก้คำผิดของ VLM โดยไม่ให้ LLM เขียนข้อความเอง

ปัญหา: qwen2.5vl อ่านผิดคนละจุดในแต่ละรอบ ("บุปผินัยนารัก น่าคบ" / "อุปนิสัยน่ารัก น่าควบคุม")
       และคำที่ผิดมักเป็นคำที่มีในพจนานุกรม ("ต่างกันทัพ") -> ตรวจด้วยพจนานุกรมไม่ได้
วิธี: OCR 3 รอบ (dpi ต่างกัน) ตัดคำ แล้วจัดแนวทุกรอบกับรอบหลัก (difflib) ช่วงไหนอย่างน้อย 2 รอบตรงกันใช้ช่วงนั้น
      ไม่มีเสียงข้างมาก -> ใช้รอบหลัก (dpi สูงสุด)

รัน: python -m pipelines.ingest.ocr_vote <source_id> [--dpis 220,180]   (รอบแรกใช้ cache เดิม)
"""
import argparse
from difflib import SequenceMatcher

import pymupdf
from pythainlp.tokenize import word_tokenize

from ..common.io_utils import read_json, write_json
from . import ocr


def _tokens(text):
    """ตัดคำแต่เก็บช่องว่าง/ขึ้นบรรทัดไว้เป็น token -> ต่อกลับได้ตรงรูปเดิม"""
    return word_tokenize(text, engine="newmm", keep_whitespace=True)


def vote(texts: list, main: int = 0) -> tuple:
    """texts = ผล OCR หลายรอบของหน้าเดียวกัน -> (ข้อความที่โหวตแล้ว, จำนวนช่วงที่เปลี่ยนจากรอบหลัก)

    ช่วงที่รอบอื่น "ทุกรอบ" เสนอข้อความเดียวกันและต่างจากรอบหลัก = เสียงข้างมาก (2 ต่อ 1) -> ใช้ข้อความนั้น
    """
    base = _tokens(texts[main])
    others = [_tokens(t) for i, t in enumerate(texts) if i != main]
    proposals = {}
    for other in others:
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, base, other, autojunk=False).get_opcodes():
            if tag != "equal":
                proposals.setdefault((i1, i2), []).append("".join(other[j1:j2]))
    chosen = sorted((i1, i2, alts[0]) for (i1, i2), alts in proposals.items()
                    if len(alts) == len(others) and len(set(alts)) == 1)
    out, pos, changed = [], 0, 0
    for i1, i2, text in chosen:
        if i1 < pos:          # ช่วงซ้อนกัน -> ข้าม (ใช้ช่วงแรก)
            continue
        out += ["".join(base[pos:i1]), text]
        pos, changed = i2, changed + 1
    out.append("".join(base[pos:]))
    return "".join(out), changed


def run(source_id, path, dpis=(220, 180), log=print):
    cache_file = ocr.CACHE_DIR / f"{source_id}.json"
    cache = read_json(cache_file)
    passes = cache.setdefault("passes", {})
    with pymupdf.open(path) as doc:
        for dpi in dpis:
            key = str(dpi)
            got = passes.setdefault(key, {})
            for p in cache["pages"]:
                if str(p["page"]) not in got:
                    got[str(p["page"])] = ocr._vlm_page(doc[p["page"]], dpi=dpi)
                    write_json(cache_file, cache)   # บันทึกทีละหน้า: หยุดกลางทางแล้วรันต่อได้
            log(f"    OCR pass dpi={dpi} {source_id}: {len(got)}/{len(cache['pages'])} หน้า")
    total = 0
    for p in cache["pages"]:
        first = p.get("pass1", p["text"])
        p["pass1"] = first
        texts = [passes[str(dpis[0])][str(p["page"])], first] + [passes[str(d)][str(p["page"])] for d in dpis[1:]]
        if any(ocr.is_meta(t) for t in texts):   # รอบไหนไม่ได้อ่านหน้า -> ไม่โหวต ใช้รอบแรก
            p["text"] = first
            continue
        p["text"], n = vote(texts, main=0)
        total += n
    cache["voted"] = {"dpis": [150, *dpis], "changed_spans": total}
    write_json(cache_file, cache)
    log(f"    OCR vote {source_id}: เปลี่ยน {total} ช่วง")
    return total


def main():
    from .sources import SOURCES
    ap = argparse.ArgumentParser()
    ap.add_argument("source_id")
    ap.add_argument("--dpis", default="220,180")
    args = ap.parse_args()
    src = next(s for s in SOURCES if s["source_id"] == args.source_id)
    dpis = tuple(int(x) for x in args.dpis.split(","))
    for n, path in enumerate(src.get("files") or [src["file"]], 1):
        cid = f"{src['source_id']}_{n}" if src.get("files") else src["source_id"]
        run(cid, path, dpis)


if __name__ == "__main__":
    main()
