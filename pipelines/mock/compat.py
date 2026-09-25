"""คะแนนความเข้ากันได้แบบ oracle (ใช้ ground truth ทั้งหมด) — ใช้สร้างเฉลยเท่านั้น ไม่ใช่ตัว matcher จริง"""
from ..common import taxonomy


def ids(xs):
    return {x["id"] for x in xs}


RULES = {}
for r in taxonomy.rules():
    sign = 1 if r["relation"] == "COMPATIBLE_WITH" else -1
    RULES[(r["a"], r["b"])] = RULES[(r["b"], r["a"])] = sign * r["weight"]


def compat(a, b):
    """คะแนนความเข้ากันได้ 'จริง' (oracle) ใช้ข้อมูล ground truth ทั้งหมด -> ใช้สร้างเฉลยเท่านั้น"""
    da, db = a["demographic"], b["demographic"]
    if da["gender"] not in db["seeking"] or db["gender"] not in da["seeking"]:
        return None, "orientation_mismatch"
    for x, y in ((a, b), (b, a)):
        if ids(x["preferences"]["avoids"]) & set(y["_ground_truth_flags"]):
            return -1.0, "red_flag_conflict"
    pa, pb = a["persona"], b["persona"]
    s = 0.0
    s += 0.25 * len(ids(pa["hobbies"]) & ids(pb["hobbies"])) / max(1, len(ids(pa["hobbies"]) | ids(pb["hobbies"])))
    s += 0.25 * (len(ids(a["preferences"]["wants"]) & ids(pb["traits"])) / len(a["preferences"]["wants"])
                 + len(ids(b["preferences"]["wants"]) & ids(pa["traits"])) / len(b["preferences"]["wants"])) / 2
    feats_a = ids(pa["traits"]) | ids(pa["comm_style"]) | {pa["attachment_style"]["id"]}
    feats_b = ids(pb["traits"]) | ids(pb["comm_style"]) | {pb["attachment_style"]["id"]}
    s += 0.2 * max(-1, min(1, sum(RULES.get((x, y), 0) for x in feats_a for y in feats_b) / 2))
    s += 0.1 * (pa["lifestyle"]["sleep"] == pb["lifestyle"]["sleep"]) + 0.1 * (pa["lifestyle"]["weekend"] == pb["lifestyle"]["weekend"])
    s += 0.1 * len(ids(pa["love_language"]) & ids(pb["love_language"])) / 2
    return round(s, 4), "ok"
