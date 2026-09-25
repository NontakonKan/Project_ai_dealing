"""แชทจำลอง + gold extraction (มี noise/PII สำหรับทดสอบขั้น cleaning)"""
from .config import ALIASES, CHAT_OPENERS, LABEL


def make_chats(users, rng, k):
    rows = []
    for u in rng.sample(users, k=k):
        p = u["persona"]
        hob = rng.sample(p["hobbies"], k=min(2, len(p["hobbies"])))
        tr = rng.sample(p["traits"], k=min(1, len(p["traits"])))
        wants = u["preferences"]["wants"][:2]
        msg = (f"{rng.choice(CHAT_OPENERS)} ปกติชอบ{' กับ '.join(rng.choice(ALIASES[h['id']] or [LABEL[h['id']]]) for h in hob)} "
               f"เป็นคน{rng.choice(ALIASES[tr[0]['id']] or [LABEL[tr[0]['id']]])} "
               f"ชอบคน{' '.join(rng.choice(ALIASES[w['id']] or [LABEL[w['id']]]) for w in wants)}")
        if rng.random() < 0.3:
            msg += " 555 😂"  # noise สำหรับขั้น cleaning
        has_pii = rng.random() < 0.15
        if has_pii:
            msg += f" แอดไลน์มาได้นะ 08{rng.randint(10000000, 99999999)}"  # PII ที่ต้องถูกลบ
        rows.append({"chat_id": f"C{len(rows)+1:04d}", "user_id": u["user_id"], "text": msg, "has_pii": has_pii,
                     "gold": {"hobbies": [h["id"] for h in hob], "traits": [t["id"] for t in tr], "wants": [w["id"] for w in wants]}})
    return rows
