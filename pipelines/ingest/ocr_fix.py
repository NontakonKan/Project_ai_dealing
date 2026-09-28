"""เลือกคำจาก OCR 2 รอบด้วย WangchanBERTa (masked LM) — ใช้เป็นตัวชี้จุดน่าสงสัย ไม่ใช่ตัวแต่งคำ

วัดจริง (7 คู่ถูก/ผิดจากหน้าวิทยานิพนธ์):
  คะแนนรวม (sum) ถูก 4/6, คะแนนเฉลี่ยต่อ token ถูก 4/7 — "จะจีบ/จะจับ" ผิดทั้งคู่ เพราะประโยคผิดก็ยังเป็นภาษาที่เป็นไปได้
กติกา: ช่วงที่ OCR 2 รอบไม่ตรงกัน -> เลือกอีกแบบเฉพาะเมื่อ sum และ mean เห็นตรงกัน และห่างเกิน MARGIN
       ที่เหลือใช้รอบหลัก และเก็บเป็นรายการให้ตรวจจากภาพ (review)
"""
from difflib import SequenceMatcher
from functools import lru_cache

from pythainlp.tokenize import word_tokenize

MLM = "airesearch/wangchanberta-base-att-spm-uncased"
CONTEXT = 30          # ตัวอักษรรอบช่วงที่ต่างกันที่ใช้ให้คะแนน
MARGIN_MEAN = 0.5     # log-prob เฉลี่ยต่อ token ต้องดีกว่าอย่างน้อยเท่านี้


@lru_cache(maxsize=1)
def _mlm():
    from transformers import AutoModelForMaskedLM, AutoTokenizer
    dev = "cpu"   # MPS แย่ GPU กับ VLM ที่ OCR อยู่ + คอมไพล์ใหม่ทุกขนาด input -> ช้ากว่า CPU มากสำหรับประโยคสั้นๆ
    return AutoTokenizer.from_pretrained(MLM), AutoModelForMaskedLM.from_pretrained(MLM).eval().to(dev), dev


def pll(text) -> tuple:
    """pseudo-log-likelihood: ปิดทีละ token แล้วดูว่าโมเดลทายกลับได้แค่ไหน -> (sum, mean)"""
    import torch
    tok, model, dev = _mlm()
    ids = tok(text, return_tensors="pt", truncation=True, max_length=128)["input_ids"][0]
    n = len(ids) - 2
    if n <= 0:
        return 0.0, 0.0
    batch = ids.repeat(n, 1)
    for i in range(n):
        batch[i, i + 1] = tok.mask_token_id
    with torch.no_grad():
        lp = torch.log_softmax(model(batch.to(dev)).logits, -1)
    scores = [lp[i, i + 1, ids[i + 1]].item() for i in range(n)]
    return sum(scores), sum(scores) / n


def _tokens(text):
    return word_tokenize(text, engine="newmm", keep_whitespace=True)


def merge(main: str, other: str) -> tuple:
    """-> (ข้อความที่เลือกแล้ว, รายการจุดที่ยังไม่แน่ใจ [(ก่อน, main, other, หลัง)])"""
    a, b = _tokens(main), _tokens(other)
    out, review = [], []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        x, y = "".join(a[i1:i2]), "".join(b[j1:j2])
        if tag == "equal":
            out.append(x)
            continue
        before = "".join(out)[-CONTEXT:]
        after = "".join(a[i2:])[:CONTEXT]
        (sx, mx), (sy, my) = pll(before + x + after), pll(before + y + after)
        if sy > sx and my > mx + MARGIN_MEAN:
            out.append(y)                      # ทั้ง sum และ mean เห็นว่าอีกรอบดีกว่าชัดเจน
        else:
            out.append(x)
            if x.strip() or y.strip():
                review.append((before[-15:], x, y, after[:15]))
    return "".join(out), review


def run(cache_id, path, log=print):
    """OCR รอบใหม่ (ตัดตราดาวน์โหลด) + เลือกคำจาก 2 รอบ -> cache.pages[].text / เก็บรอบเดิมใน pass1, จุดไม่แน่ใจใน review"""
    import pymupdf
    from ..common.io_utils import read_json, write_json
    from . import ocr, ocr_image
    cache_file = ocr.CACHE_DIR / f"{cache_id}.json"
    cache = read_json(cache_file)
    with pymupdf.open(path) as doc:                    # รอบ 1: OCR ให้ครบก่อน (ใช้ GPU)
        for p in cache["pages"]:
            p.setdefault("pass1", p["text"])
            if "pass_cut" not in p:
                p["pass_cut"] = ocr_image.ocr_page(doc[p["page"]], ocr.VLM_MODEL, ocr.VLM_PROMPT)
                write_json(cache_file, cache)          # บันทึกทีละหน้า หยุดกลางทางแล้วรันต่อได้
                log(f"    OCR {cache_id} หน้า {p['page'] + 1}/{len(cache['pages'])}")
    for p in cache["pages"]:                           # รอบ 2: เลือกคำจาก 2 รอบ (CPU)
        if ocr.is_meta(p["pass_cut"]):
            p["text"], p["review"] = p["pass1"], []
        elif ocr.is_meta(p["pass1"]):
            p["text"], p["review"] = p["pass_cut"], []
        else:
            p["text"], p["review"] = merge(p["pass_cut"], p["pass1"])
        log(f"    {cache_id} หน้า {p['page'] + 1}/{len(cache['pages'])}: จุดไม่แน่ใจ {len(p['review'])}")
    cache["fixed"] = {"method": "OCR ตัดตราดาวน์โหลด + WangchanBERTa เลือกคำจาก 2 รอบ", "review_spans": sum(len(p["review"]) for p in cache["pages"])}
    write_json(cache_file, cache)


def main():
    import argparse
    from .sources import SOURCES
    ap = argparse.ArgumentParser(description="python -m pipelines.ingest.ocr_fix <source_id> [--parts 5,6]")
    ap.add_argument("source_id")
    ap.add_argument("--parts", help="เฉพาะไฟล์ลำดับที่ (เอกสารหลายไฟล์)")
    args = ap.parse_args()
    src = next(s for s in SOURCES if s["source_id"] == args.source_id)
    files = src.get("files") or [src["file"]]
    parts = {int(x) for x in args.parts.split(",")} if args.parts else set(range(1, len(files) + 1))
    for n, path in enumerate(files, 1):
        if n in parts:
            run(f"{src['source_id']}_{n}" if src.get("files") else src["source_id"], path)


if __name__ == "__main__":
    main()
