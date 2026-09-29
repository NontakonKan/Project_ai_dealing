"""สุ่มตรวจ concept tag: เลือกคู่ (chunk, concept) แบบสุ่มคงที่ แล้วแสดงคำที่ทำให้ติด tag พร้อมบริบท

concept ใช้เชื่อม chunk กับ Graph (ABOUT) -> tag ผิดทำให้ Graph ดึง chunk ไม่เกี่ยวมาตอบ
ผลตรวจ (correct: true/false + note) เก็บที่ data/eval/concept_tag_audit.json แล้วคำนวณ precision

รัน:
  python -m pipelines.ingest.tag_audit sample [--n 50]   # สร้างรายการให้ตรวจ (ไม่ทับช่อง correct ที่ตรวจแล้ว)
  python -m pipelines.ingest.tag_audit report            # precision จากรายการที่ตรวจแล้ว
"""
import argparse
import json
import random

from ..common.paths import DATA, PROCESSED
from .tagger import CONTEXT_WINDOW, _ok, _patterns

AUDIT = DATA / "eval" / "concept_tag_audit.json"
SEED = 20260928


def _evidence(text, patterns):
    """คำแรกที่ทำให้ติด concept นี้ (ผ่านกฎบริบทแล้ว) + ข้อความรอบๆ"""
    for pat, rule in patterns:
        for m in pat.finditer(text):
            if _ok(text, m, rule):
                a, b = max(0, m.start() - CONTEXT_WINDOW), m.end() + CONTEXT_WINDOW
                return m.group(), text[a:b].replace("\n", " ")
    return None, None


def sample(n):
    chunks = [json.loads(l) for l in open(PROCESSED / "book_chunks.jsonl", encoding="utf-8")]
    pairs = [(c, cid) for c in chunks for cid in c.get("concepts", [])]
    concept_pats, _ = _patterns()
    old = {(r["chunk_id"], r["concept"]): r for r in json.loads(AUDIT.read_text(encoding="utf-8"))} if AUDIT.exists() else {}
    rows = []
    for c, cid in random.Random(SEED).sample(pairs, min(n, len(pairs))):
        kw, ctx = _evidence(c["text"], concept_pats.get(cid, []))
        prev = old.get((c["chunk_id"], cid), {})
        rows.append({"chunk_id": c["chunk_id"], "source_id": c["source_id"], "concept": cid, "keyword": kw,
                     "context": ctx, "correct": prev.get("correct"), "note": prev.get("note", "")})
    AUDIT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} คู่ จากทั้งหมด {len(pairs)} -> {AUDIT}")


def report():
    rows = json.loads(AUDIT.read_text(encoding="utf-8"))
    done = [r for r in rows if r["correct"] is not None]
    ok = sum(r["correct"] for r in done)
    print(f"ตรวจแล้ว {len(done)}/{len(rows)}  ถูก {ok}  precision {ok / max(1, len(done)):.1%}")
    for r in done:
        if not r["correct"]:
            print(f"  ✗ {r['concept']:22} '{r['keyword']}' — {r['note']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "report"])
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()
    sample(args.n) if args.cmd == "sample" else report()


if __name__ == "__main__":
    main()
