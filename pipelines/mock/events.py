"""สร้างเหตุการณ์ unmatch / matched / pass และสะท้อน feedback ลงโปรไฟล์ (ผ่าน feedback.policy เดียวกับระบบจริง)"""
from datetime import datetime, timedelta

from ..feedback.apply import apply_unmatch
from ..feedback.policy import route_unmatch
from .compat import compat
from .config import ALIASES, BREAKUP_TEMPLATES
from .sampling import conf

P_UNMATCH_FLAG = 0.85
P_UNMATCH_APPEARANCE = 0.6    # A ไม่ชอบรูปลักษณ์ที่ B เป็นจริง -> มีโอกาสเลิกคุยด้วยเหตุผลนี้


def _appearance_reasons(a, b):
    """รูปลักษณ์จริงของ B ที่ตรงกับสิ่งที่ A ไม่ชอบ"""
    avoid = {x["id"] for x in a["preferences"]["avoids"]}
    return [x for x in b["_ground_truth_appearance"] if x in avoid]


def make_events(users, rng, today):
    events, n = [], 0
    for a in users:
        cands = [b for b in users if b is not a and compat(a, b)[0] is not None]
        for b in rng.sample(cands, k=min(len(cands), rng.randint(0, 3))):
            n += 1
            ts = datetime.combine(today - timedelta(days=rng.randint(1, 90)), datetime.min.time()) + timedelta(hours=rng.randint(8, 23))
            base = {"event_id": f"E{n:04d}", "from_user": a["user_id"], "about_user": b["user_id"], "timestamp": ts.isoformat()}
            flags = b["_ground_truth_flags"]
            looks = _appearance_reasons(a, b)
            picked_rf = rng.sample(flags, k=min(len(flags), rng.randint(1, 2))) if flags and rng.random() < P_UNMATCH_FLAG else []
            picked_app = looks if looks and rng.random() < P_UNMATCH_APPEARANCE else []
            if picked_rf or picked_app:
                reason = " ".join(rng.choice(ALIASES[f]) + ("ไป" if f in picked_app else "") for f in picked_rf + picked_app)
                gold = {"red_flags": [{"id": f, "severity": conf(rng, 0.6, 1.0)} for f in picked_rf],
                        "appearance": [{"id": f, "severity": conf(rng, 0.4, 0.8)} for f in picked_app], "hygiene": []}
                events.append({**base, "type": "unmatch", "raw_reason": rng.choice(BREAKUP_TEMPLATES).format(r=reason),
                               "gold_extracted": gold})
            elif compat(a, b)[0] > 0.35:
                events.append({**base, "type": "matched", "raw_reason": "คุยกันถูกคอดี", "gold_extracted": {}})
            else:
                events.append({**base, "type": "pass", "raw_reason": "ไม่ค่อยตรงสเปก", "gold_extracted": {}})
    return events


def apply_feedback(users, events):
    """สะท้อน unmatch ลงโปรไฟล์ด้วย policy เดียวกับระบบจริง (รูปลักษณ์เก็บที่ผู้พูดเท่านั้น)"""
    by_id = {u["user_id"]: u for u in users}
    for e in sorted(events, key=lambda e: e["timestamp"]):
        if e["type"] == "unmatch":
            apply_unmatch(by_id[e["from_user"]], by_id[e["about_user"]], route_unmatch(e["gold_extracted"]), e["event_id"])
