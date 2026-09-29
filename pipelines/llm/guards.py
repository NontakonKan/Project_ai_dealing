"""ด่านหลัง LLM (rule-based) — แก้ข้อผิดพลาดที่ schema/validate จับไม่ได้

1. misclassified_appearance: red flag ที่ evidence เป็นคำรูปลักษณ์ (เช่น rf:disrespect + "อ้วนไป") -> ทิ้ง
   (validate ผ่านเพราะ "อ้วนไป" มีในข้อความจริง แต่ความหมายไม่ใช่พฤติกรรม)
2. appearance_id_corrected: LLM ใส่รหัสรูปลักษณ์ผิด (เช่น "อ้วน" -> body:athletic) -> แก้ตาม keyword detector
3. red_flag_id_corrected: evidence ตรงกับ alias ของ red flag ตัวอื่น (เช่น "หายเงียบ" -> rf:ghosting แต่ alias ของ rf:stonewalling) -> แก้
4. fallback_added: คำรูปลักษณ์/สุขอนามัยที่ LLM ตกหล่นในเหตุผลเลิกคุย -> เติมจาก keyword detector
"""
from collections import Counter

from ..common import taxonomy
from ..feedback import sensitive

FALLBACK_SEVERITY = 0.6


def drop_appearance_red_flags(clean: dict, fields=("red_flags", "avoids")) -> Counter:
    stats, rf = Counter(), set(taxonomy.ids("red_flags"))
    for f in fields:
        keep = []
        for it in clean.get(f, []):
            if it["id"] in rf and sensitive.is_appearance(it.get("evidence", "")):
                stats["misclassified_appearance"] += 1
            else:
                keep.append(it)
        if f in clean:
            clean[f] = keep
    return stats


def correct_appearance_ids(clean: dict, fields=("appearance", "hygiene", "self_described", "wants", "avoids")) -> Counter:
    """evidence ของรายการรูปลักษณ์ต้องตรงกับรหัส ถ้า keyword detector ชี้รหัสอื่นในหมวดเดียวกัน -> แก้ให้ถูก"""
    stats, appearance = Counter(), taxonomy.appearance_ids()
    for f in fields:
        out, seen = [], set()
        for it in clean.get(f, []):
            if it["id"] in appearance:
                group = taxonomy.group_of(it["id"])
                hits = [h["id"] for h in sensitive.detect(it.get("evidence", ""), mode="unmatch")
                        if taxonomy.group_of(h["id"]) == group]
                if hits and it["id"] not in hits:
                    it = {**it, "id": hits[0], "corrected_from": it["id"]}
                    stats["appearance_id_corrected"] += 1
            if it["id"] not in seen:
                seen.add(it["id"])
                out.append(it)
        if f in clean:
            clean[f] = out
    return stats


def correct_red_flag_ids(clean: dict, fields=("red_flags", "avoids")) -> Counter:
    stats, rf_alias = Counter(), sorted(((a.lower(), tid) for tid, als in taxonomy.aliases().items()
                                          if tid.startswith("rf:") for a in als), key=lambda x: -len(x[0]))
    for f in fields:
        out, seen = [], set()
        for it in clean.get(f, []):
            if it["id"].startswith("rf:"):
                ev = (it.get("evidence") or "").lower()
                owners = {tid for a, tid in rf_alias if a in ev}
                if owners and it["id"] not in owners:
                    it = {**it, "id": next(tid for a, tid in rf_alias if a in ev), "corrected_from": it["id"]}
                    stats["red_flag_id_corrected"] += 1
            if it["id"] not in seen:
                seen.add(it["id"])
                out.append(it)
        if f in clean:
            clean[f] = out
    return stats


def fill_unmatch_appearance(clean: dict, reason: str) -> Counter:
    stats = Counter()
    groups = {"appearance": set(taxonomy.ids("body_types")) | set(taxonomy.ids("skin_tones")),
              "hygiene": set(taxonomy.ids("hygiene"))}
    for hit in sensitive.detect(reason, mode="unmatch"):
        field = next(f for f, ids in groups.items() if hit["id"] in ids)
        if hit["id"] not in {x["id"] for x in clean.setdefault(field, [])}:
            clean[field].append({**hit, "severity": FALLBACK_SEVERITY, "by": "keyword"})
            stats["fallback_added"] += 1
    return stats


def drop_invalid_avoids(clean: dict, text: str = "") -> Counter:
    """ลบ avoids ที่หลักฐานเป็นคำบอกชอบ หรือนิสัยเชิงบวกที่ LLM สับสนใส่เป็น red flag (เช่น "นิ่ง" -> rf:possessive)"""
    stats = Counter()
    avoids = clean.get("avoids", [])
    if not avoids:
        return stats
    negative_cues = ("ไม่ชอบ", "ไม่เอา", "เกลียด", "เบื่อ", "ห้าม", "อย่า", "รับไม่ได้", "ไม่โอเค", "ไม่ดี", "ไม่ค่อยชอบ")
    positive_cues = ("ชอบ", "อยากได้", "สเปก", "สเป็ค", "ขอคน", "หาคน")

    keep = []
    for it in avoids:
        ev = (it.get("evidence") or "").strip()
        # ถ้า evidence เป็นคำว่า "นิ่ง" หรือ "ใจเย็น" -> แท้จริงคือ trait:calm
        if any(w in ev for w in ("นิ่ง", "ใจเย็น", "สงบ")):
            wants = clean.setdefault("wants", [])
            if not any(x["id"] == "trait:calm" for x in wants):
                wants.append({"id": "trait:calm", "evidence": ev})
            stats["avoid_moved_to_wants"] += 1
            continue

        if text and ev:
            idx = text.find(ev)
            if idx >= 0:
                before = text[max(0, idx - 15):idx + len(ev)]
                has_neg = any(c in before for c in negative_cues)
                has_pos = any(c in before for c in positive_cues)
                if has_pos and not has_neg:
                    stats["dropped_positive_from_avoids"] += 1
                    continue
        keep.append(it)
    clean["avoids"] = keep
    return stats


def drop_faculty_hallucinations(clean: dict, text: str = "") -> Counter:
    """ลบรายการที่ evidence ไปตรงกับชื่อคณะ ซึ่งควรสกัดด้วย faculty parser ไม่ใช่กลายเป็น hygiene หรือนิสัย"""
    stats = Counter()
    if not text:
        return stats
    from ..profile import faculty
    parsed = faculty.parse(text)
    spans = parsed.get("spans", [])
    if not spans:
        return stats
    for field in ("hobbies", "traits", "comm_style", "self_described", "wants", "avoids"):
        keep = []
        for it in clean.get(field, []):
            ev = (it.get("evidence") or "").strip()
            if any(s in ev or ev in s for s in spans):
                stats["dropped_faculty_hallucination"] += 1
            else:
                keep.append(it)
        if field in clean:
            clean[field] = keep
    return stats
