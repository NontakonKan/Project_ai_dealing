"""คะแนนเชิงโครงสร้างของคู่ (A, B) จากกราฟ + เหตุผลที่อ่านได้ (graph_fact) สำหรับ LLM

feature ตรงกับ query ของ Graph:
  shared      -> hobby / love_language ร่วม
  rule-paths  -> theory (HAS_TRAIT - COMPATIBLE/CONFLICTS - HAS_TRAIT)
  reports     -> red flag: A AVOIDS rf ∩ B REPORTED_AS rf
  + prefers (A PREFERS trait ∩ B HAS_TRAIT), lifestyle, appearance (PREFERS/AVOIDS ∩ SELF_DESCRIBED)
"""
from .view import RULE_SIGN

# น้ำหนัก feature (ตั้งเอง ไม่ได้คัดลอกจากตัวสร้างเฉลย pipelines/mock/compat.py)
GRAPH_WEIGHTS = {"prefers": 0.35, "theory": 0.25, "hobby": 0.20, "love_language": 0.10, "lifestyle": 0.10}

APPEARANCE_PREFIX = ("body:", "skin:", "hygiene:")


def _jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def _prefers(g, a, b):
    wants = {t: p.get("weight", 1.0) for t, p in g.rel(a, "PREFERS").items() if t.startswith("trait:")}
    total = sum(wants.values())
    return sum(w for t, w in wants.items() if t in g.rel(b, "HAS_TRAIT")) / total if total else 0.0


def _appearance(g, a, b):
    declared = set(g.rel(b, "SELF_DESCRIBED"))
    if not declared:
        return 0.0
    plus = sum(p.get("weight", 0) for t, p in g.rel(a, "PREFERS").items() if t in declared)
    minus = sum(p.get("weight", 0) for t, p in g.rel(a, "AVOIDS").items() if t in declared)
    return max(-1.0, min(1.0, plus - minus))


def _lifestyle(g, a, b):
    same = [g.prop(a, k) == g.prop(b, k) for k in ("lifestyle_sleep", "lifestyle_weekend")
            if g.prop(a, k) not in (None, "unknown") and g.prop(b, k) not in (None, "unknown")]
    return sum(same) / 2   # ไม่รู้ = ไม่ได้คะแนน (ไม่นับ unknown == unknown)


def _redflags(g, a, b):
    """red flag ที่ฝั่งหนึ่งหลีกเลี่ยงและอีกฝั่งถูกรายงาน (REPORTED_AS มีเฉพาะที่ผ่านเกณฑ์ >= 3 คน)"""
    hits = []
    for x, y in ((a, b), (b, a)):
        for rf, p in g.rel(x, "AVOIDS").items():
            if rf.startswith("rf:") and rf in g.rel(y, "REPORTED_AS"):
                hits.append({"avoider": x, "reported": y, "id": rf, "weight": p.get("weight", 1.0),
                             "report_count": g.rel(y, "REPORTED_AS")[rf].get("report_count")})
    return hits


def pair(g, a, b, facts=False) -> dict:
    ta, tb = set(g.rel(a, "HAS_TRAIT")), set(g.rel(b, "HAS_TRAIT"))
    rule_hits = [(x, y, *g.rules[(x, y)]) for x in ta for y in tb if (x, y) in g.rules]
    f = {
        "prefers": (_prefers(g, a, b) + _prefers(g, b, a)) / 2,
        "theory": max(-1.0, min(1.0, sum(RULE_SIGN[r] * w for _, _, r, w, _ in rule_hits) / 2)),
        "hobby": _jaccard(g.rel(a, "LIKES"), g.rel(b, "LIKES")),
        "love_language": len(set(g.rel(a, "HAS_LOVE_LANGUAGE")) & set(g.rel(b, "HAS_LOVE_LANGUAGE"))) / 2,
        "lifestyle": _lifestyle(g, a, b),
    }
    out = {"features": {k: round(v, 4) for k, v in f.items()},
           "graph_score": round(sum(GRAPH_WEIGHTS[k] * v for k, v in f.items()), 4),
           "appearance": round((_appearance(g, a, b) + _appearance(g, b, a)) / 2, 4),
           "redflags": _redflags(g, a, b)}
    if facts:
        out["facts"] = _facts(g, a, b, rule_hits, out["redflags"])
    return out


def _facts(g, a, b, rule_hits, redflags) -> list:
    """ประโยคที่อ่านรู้เรื่อง (ใช้เป็น graph_fact ใน RetrievalResult) — ไม่เปิดเผยรูปลักษณ์/สีผิว"""
    lab = g.label
    out = []
    shared = sorted(set(g.rel(a, "LIKES")) & set(g.rel(b, "LIKES")))
    if shared:
        out.append({"id": f"shared_hobby:{a}:{b}", "text": "ทั้งคู่ชอบ: " + ", ".join(lab(h) for h in shared),
                    "path": [a, "LIKES", *shared, "LIKES", b]})
    for x, y in ((a, b), (b, a)):
        matched = [t for t in g.rel(x, "PREFERS") if t.startswith("trait:") and t in g.rel(y, "HAS_TRAIT")]
        if matched:
            who = "A" if x == a else "B"
            out.append({"id": f"prefers:{x}:{y}", "text": f"{who} อยากได้คนที่ {', '.join(lab(t) for t in matched)} "
                        f"— อีกฝ่ายมีนิสัยนี้", "path": [x, "PREFERS", *matched, "HAS_TRAIT", y]})
    for x, y, rel, w, reason in rule_hits:
        out.append({"id": f"rule:{x}:{y}", "text": f"({lab(x)}) -[{rel}]-> ({lab(y)})" + (f": {reason}" if reason else ""),
                    "path": [a, "HAS_TRAIT", x, rel, y, "HAS_TRAIT", b], "concepts": [x, y]})
    for h in redflags:
        who = "B" if h["reported"] == b else "A"
        out.append({"id": f"redflag:{h['reported']}:{h['id']}", "concepts": [h["id"]],
                    "text": f"⚠️ {who} ถูกรายงานว่า {lab(h['id'])} ({h['report_count']} คน) ซึ่งอีกฝ่ายหลีกเลี่ยง",
                    "path": [h["avoider"], "AVOIDS", h["id"], "REPORTED_AS", h["reported"]]})
    return out
