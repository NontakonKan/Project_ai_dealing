"""วัดคุณภาพ OCR เทียบกับหน้าที่ถอดด้วยมือจากภาพ (data/eval/ocr_gold/<cache_id>_p<page>.txt)

CER = ระยะแก้ไขระดับตัวอักษร / ความยาวเฉลย (ตัดช่องว่างทิ้งทั้งสองฝั่ง เพราะ OCR จัดบรรทัด/ตารางต่างกันได้)
WER = ระยะแก้ไขระดับคำ (ตัดคำด้วย PyThaiNLP) / จำนวนคำเฉลย

รัน: python -m pipelines.ingest.ocr_eval            # ใช้ข้อความใน cache OCR ปัจจุบัน
"""
import re

from ..common.paths import DATA
from .ocr import CACHE_DIR, RE_STAMP

GOLD_DIR = DATA / "eval" / "ocr_gold"


def _norm(text):
    text = RE_STAMP.sub("", text or "")
    return re.sub(r"\s+", "", text)


def edit_distance(a, b) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def cer(hyp, gold) -> float:
    g = _norm(gold)
    return edit_distance(_norm(hyp), g) / max(1, len(g))


def wer(hyp, gold) -> float:
    from pythainlp.tokenize import word_tokenize
    tok = lambda t: [w for w in word_tokenize(_norm(t), engine="newmm")]
    g = tok(gold)
    return edit_distance(tok(hyp), g) / max(1, len(g))


def gold_pages() -> dict:
    """{(cache_id, page_index): เฉลย}"""
    out = {}
    for f in sorted(GOLD_DIR.glob("*_p*.txt")):
        cid, page = f.stem.rsplit("_p", 1)
        out[(cid, int(page) - 1)] = f.read_text(encoding="utf-8")
    return out


def evaluate(get_text) -> dict:
    """get_text(cache_id, page_index) -> ข้อความที่จะวัด"""
    rows = {}
    for (cid, page), gold in gold_pages().items():
        hyp = get_text(cid, page)
        rows[f"{cid} p{page + 1}"] = {"cer": round(cer(hyp, gold), 4), "wer": round(wer(hyp, gold), 4)}
    rows["mean"] = {k: round(sum(r[k] for r in rows.values()) / len(rows), 4) for k in ("cer", "wer")}
    return rows


def from_cache(field="text"):
    from ..common.io_utils import read_json
    return lambda cid, page: read_json(CACHE_DIR / f"{cid}.json")["pages"][page].get(field) or ""


def main():
    for name, row in evaluate(from_cache()).items():
        print(f"  {name:40} CER {row['cer']:.2%}  WER {row['wer']:.2%}")


if __name__ == "__main__":
    main()
