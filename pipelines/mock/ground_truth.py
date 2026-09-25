"""เฉลยคู่ที่ควรแมตช์ (relevant) และต้องกรองออก (must_exclude) สำหรับ Evaluation"""
from .compat import compat


def make_ground_truth(users, rng, top=5):
    active = [u for u in users if u["consent"]["matching"]]
    out = []
    for a in active:
        scored = [(b["user_id"], *compat(a, b)) for b in active if b is not a]
        ok = sorted([s for s in scored if s[1] is not None and s[2] == "ok"], key=lambda s: -s[1])
        bad = [s for s in scored if s[2] == "red_flag_conflict"]
        out.append({"user_id": a["user_id"],
                    "relevant": [{"user_id": x, "score": s} for x, s, _ in ok[:top]],
                    "must_exclude": [x for x, _, _ in bad],
                    "hard_negative_note": "must_exclude = อีกฝ่ายมี red flag ที่ผู้ใช้ avoid (ระบบต้องกรองออก/หักคะแนน)"})
    return out
