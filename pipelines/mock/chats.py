"""แชทจำลอง + gold extraction (มี noise/PII สำหรับทดสอบขั้น cleaning + ประโยครูปลักษณ์)"""
from .config import ALIASES, CHAT_OPENERS, LABEL

P_SELF_DESCRIBE, P_APPEARANCE_WANT = 0.3, 0.3


def _say(tid, rng):
    return rng.choice(ALIASES[tid] or [LABEL[tid]])


def make_chats(users, rng, k):
    rows = []
    for u in rng.sample(users, k=k):
        p = u.get("_ground_truth_persona", u["persona"])   # แชท = สิ่งที่ผู้ใช้พูดจริง (บุคลิกจริง)
        hob = rng.sample(p["hobbies"], k=min(2, len(p["hobbies"])))
        tr = rng.sample(p["traits"], k=min(1, len(p["traits"])))
        trait_wants = [w for w in u.get("_ground_truth_wants", u["preferences"]["wants"]) if w["id"].startswith("trait:")][:2]
        app_wants = [w for w in u["preferences"]["wants"] if w["id"].startswith(("body:", "skin:"))][:1]
        wants = trait_wants + (app_wants if rng.random() < P_APPEARANCE_WANT else [])
        declared = u["appearance"]["self_described"][:1] if rng.random() < P_SELF_DESCRIBE else []
        msg = (f"{rng.choice(CHAT_OPENERS)} ปกติชอบ{' กับ '.join(_say(h['id'], rng) for h in hob)} "
               f"เป็นคน{_say(tr[0]['id'], rng)} "
               + (f"เราเป็นคน{_say(declared[0]['id'], rng)}นะ " if declared else "")
               + f"ชอบคน{' '.join(_say(w['id'], rng) for w in wants)}")
        if rng.random() < 0.3:
            msg += " 555 😂"  # noise สำหรับขั้น cleaning
        has_pii = rng.random() < 0.15
        if has_pii:
            msg += f" แอดไลน์มาได้นะ 08{rng.randint(10000000, 99999999)}"  # PII ที่ต้องถูกลบ
        rows.append({"chat_id": f"C{len(rows)+1:04d}", "user_id": u["user_id"], "text": msg, "has_pii": has_pii,
                     "gold": {"hobbies": [h["id"] for h in hob], "traits": [t["id"] for t in tr],
                              "wants": [w["id"] for w in wants], "self_described": [d["id"] for d in declared]}})
    return rows
