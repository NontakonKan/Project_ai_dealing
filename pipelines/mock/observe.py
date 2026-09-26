"""จำลอง "โปรไฟล์ที่ระบบมองเห็น" จากบุคลิกจริง

ปัญหาที่แก้: ถ้าเฉลย (compat) กับ retriever เห็น feature ชุดเดียวกันเป๊ะ Graph จะชนะเพราะ leakage ไม่ใช่เพราะดีกว่า
ของจริง: โปรไฟล์มาจาก LLM สกัดแชท -> ตกหล่น + ผิดบ้าง + บางเรื่องผู้ใช้ไม่เคยพูด

  _ground_truth_persona / _ground_truth_wants  = บุคลิกจริง (ใช้สร้างเฉลยเท่านั้น)
  persona / preferences.wants                  = สิ่งที่ระบบรู้ (ใช้ทำ Dense/Graph)
"""
import copy

from .config import ALL_TRAITS, HOBBIES

P_MISS = {"hobbies": 0.30, "traits": 0.35, "comm_style": 0.30, "love_language": 0.40, "wants": 0.30}
P_WRONG = 0.10          # สกัดผิด: เพิ่ม hobby/trait ที่ไม่ได้เป็นจริง
P_ATTACH_WRONG = 0.25   # attachment ประเมินจากแชทยาก
P_LIFESTYLE_UNKNOWN = 0.30


def observe(user, rng):
    truth_p, truth_w = copy.deepcopy(user["persona"]), copy.deepcopy(user["preferences"]["wants"])
    p = user["persona"]
    for field in ("hobbies", "traits", "comm_style", "love_language"):
        kept = [x for x in p[field] if rng.random() >= P_MISS[field]]
        p[field] = kept or p[field][:1] * (field != "love_language")
    if rng.random() < P_WRONG:
        extra = rng.choice([h for h in HOBBIES if h not in {x["id"] for x in p["hobbies"]}])
        p["hobbies"].append({"id": extra, "confidence": 0.5, "evidence_count": 1, "last_seen": p["hobbies"][0]["last_seen"]})
    if rng.random() < P_WRONG:
        extra = rng.choice([t for t in ALL_TRAITS if t not in {x["id"] for x in p["traits"]}])
        p["traits"].append({"id": extra, "confidence": 0.45, "evidence_count": 1})
    if rng.random() < P_ATTACH_WRONG:
        p["attachment_style"] = {"id": rng.choice(["attach:secure", "attach:anxious", "attach:avoidant", "attach:fearful"]),
                                 "confidence": 0.35}
    for k in ("sleep", "weekend"):
        if rng.random() < P_LIFESTYLE_UNKNOWN:
            p["lifestyle"][k] = "unknown"
    wants = user["preferences"]["wants"]
    user["preferences"]["wants"] = [w for w in wants if not w["id"].startswith("trait:") or rng.random() >= P_MISS["wants"]]
    user["_ground_truth_persona"], user["_ground_truth_wants"] = truth_p, truth_w
