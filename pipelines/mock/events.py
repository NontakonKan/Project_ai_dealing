"""สร้างเหตุการณ์ unmatch / matched / pass และสะท้อน feedback ลงโปรไฟล์"""
from datetime import datetime, timedelta

from .compat import compat
from .config import ALIASES, BREAKUP_TEMPLATES
from .sampling import conf


REPORT_THRESHOLD = 3  # กันการกลั่นแกล้ง: ต้องมีผู้รายงาน >= 3 คน reported_trait ถึงใช้ได้


def make_events(users, rng, today):
    events, n = [], 0
    for a in users:
        cands = [b for b in users if b is not a and compat(a, b)[0] is not None]
        for b in rng.sample(cands, k=min(len(cands), rng.randint(0, 3))):
            n += 1
            ts = datetime.combine(today - timedelta(days=rng.randint(1, 90)), datetime.min.time()) + timedelta(hours=rng.randint(8, 23))
            flags = b["_ground_truth_flags"]
            if flags and rng.random() < 0.85:
                picked = rng.sample(flags, k=min(len(flags), rng.randint(1, 2)))
                reason = " ".join(rng.choice(ALIASES[f]) for f in picked)
                events.append({"event_id": f"E{n:04d}", "type": "unmatch", "from_user": a["user_id"], "about_user": b["user_id"],
                               "timestamp": ts.isoformat(), "raw_reason": rng.choice(BREAKUP_TEMPLATES).format(r=reason),
                               "gold_extracted": [{"id": f, "severity": conf(rng, 0.6, 1.0)} for f in picked]})
            elif compat(a, b)[0] > 0.35:
                events.append({"event_id": f"E{n:04d}", "type": "matched", "from_user": a["user_id"], "about_user": b["user_id"],
                               "timestamp": ts.isoformat(), "raw_reason": "คุยกันถูกคอดี", "gold_extracted": []})
            else:
                events.append({"event_id": f"E{n:04d}", "type": "pass", "from_user": a["user_id"], "about_user": b["user_id"],
                               "timestamp": ts.isoformat(), "raw_reason": "ไม่ค่อยตรงสเปก", "gold_extracted": []})
    return events


def apply_feedback(users, events):
    """สะท้อนผลของ unmatch ลงโปรไฟล์ (avoids ของผู้แจ้ง + reported_traits ของอีกฝ่าย)"""
    by_id = {u["user_id"]: u for u in users}
    for e in sorted(events, key=lambda e: e["timestamp"]):
        if e["type"] != "unmatch":
            continue
        a, b = by_id[e["from_user"]], by_id[e["about_user"]]
        for x in e["gold_extracted"]:
            cur = next((v for v in a["preferences"]["avoids"] if v["id"] == x["id"]), None)
            if cur:
                cur["weight"] = round(1 - (1 - cur["weight"]) * (1 - x["severity"]), 3)  # noisy-OR สะสม
                cur["count"] += 1
                cur["source"] = f"breakup:{e['event_id']}"
            else:
                a["preferences"]["avoids"].append({"id": x["id"], "weight": x["severity"], "source": f"breakup:{e['event_id']}", "count": 1})
            rep = next((v for v in b["reported_traits"] if v["id"] == x["id"]), None)
            if rep:
                rep["report_count"] += 1
            else:
                b["reported_traits"].append({"id": x["id"], "report_count": 1})
    for u in users:
        for r in u["reported_traits"]:
            r["usable"] = r["report_count"] >= REPORT_THRESHOLD
