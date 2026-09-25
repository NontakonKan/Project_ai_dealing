"""metric คุณภาพ (คู่กับ metric เวลา/resource จาก ollama_client + resources)"""


def set_prf(pred: set, gold: set) -> dict:
    tp = len(pred & gold)
    return {"tp": tp, "fp": len(pred - gold), "fn": len(gold - pred)}


def micro(rows) -> dict:
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def extraction_score(extracted: dict, gold: dict) -> dict:
    """เทียบเฉพาะ field ที่มีเฉลย"""
    out = {"tp": 0, "fp": 0, "fn": 0}
    for f, gold_ids in gold.items():
        s = set_prf({x["id"] for x in extracted.get(f, [])}, set(gold_ids))
        for k in out:
            out[k] += s[k]
    return out


def false_red_flags(extracted: dict, gold: dict) -> int:
    """red flag ที่ทายเกินเฉลย (เช่น "อ้วนไป" -> rf:disrespect) — เป้าหมาย = 0"""
    if "red_flags" not in gold:
        return 0
    return len({x["id"] for x in extracted.get("red_flags", [])} - set(gold["red_flags"]))


def rag_score(answer: str, cites: dict, q: dict) -> dict:
    if not q["answerable"]:
        return {"keyword_recall": None, "correct_abstain": cites["abstained"], "cited": cites["n_cited"] > 0}
    kws = q["expected_keywords"]
    hit = sum(1 for k in kws if k.lower() in answer.lower())
    return {"keyword_recall": round(hit / len(kws), 3), "correct_abstain": not cites["abstained"],
            "cited": cites["n_cited"] > 0, "invalid_cite": bool(cites["invalid"])}
