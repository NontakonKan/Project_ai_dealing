"""โปรไฟล์ผู้ใช้จริง: สร้าง / merge ผลสกัดจากแชท / decay / เพดานขนาด / summaries

schema เดียวกับ data/mock/users.json -> Graph, Dense, Hybrid ใช้ได้ทันที
ข้อมูลไม่โตตามจำนวนแชท: รายการเดิมเพิ่มแค่ confidence/evidence_count, เกินเพดานตัดตัวที่ confidence ต่ำสุด
"""
import time
from datetime import date

from pipelines.common import taxonomy
from pipelines.feedback import policy

from .config import DECAY_HALF_LIFE_DAYS, MAX_HOBBIES, MAX_TRAITS, MIN_CONFIDENCE

CONF_NEW, CONF_STEP = 0.6, 0.15
GENDER = {"ชาย": "M", "หญิง": "F", "อื่นๆ": "NB"}


def new_profile(user_id, display_name):
    today = str(date.today())
    return {"user_id": user_id, "display_name": display_name, "source": "line",
            "demographic": {"age": None, "gender": None, "seeking": [], "faculty": "", "campus": "หาดใหญ่"},
            "persona": {"hobbies": [], "traits": [], "comm_style": [], "love_language": [],
                        "lifestyle": {"sleep": "unknown", "social_energy": "unknown", "weekend": "unknown"},
                        "love_components": {}},
            "appearance": {"self_described": [], "consent_sensitive": False, "pending_consent": []},
            "preferences": {"wants": [], "avoids": [], "age_range": [18, 30]},
            "values": {"self": {}, "wants": {}, "self_text": [], "want_text": []},
            "reported_traits": [], "summaries": {},
            "consent": {"matching": False, "updated_at": today}, "profile_completeness": 0.0}


def _bump(items, tid, key="confidence"):
    today = str(date.today())
    cur = next((x for x in items if x["id"] == tid), None)
    if cur:
        cur[key] = round(min(0.95, cur.get(key, CONF_NEW) + CONF_STEP), 2)
        cur["evidence_count"] = cur.get("evidence_count", 1) + 1
        cur["last_seen"] = today
    else:
        items.append({"id": tid, key: CONF_NEW, "evidence_count": 1, "last_seen": today})


def _cap(items, n, key="confidence"):
    items.sort(key=lambda x: -x.get(key, 0))
    del items[n:]


def merge_extraction(profile, extracted):
    """ผลจาก pipelines.llm.tasks.extract_profile -> โปรไฟล์ (คืนรายการที่จำได้ใหม่ ไว้ให้บอทพูดถึง)"""
    p, learned = profile["persona"], []
    for field, target in (("hobbies", p["hobbies"]), ("traits", p["traits"]), ("comm_style", p["comm_style"])):
        for it in extracted.get(field, []):
            _bump(target, it["id"])
            learned.append(it["id"])
    for it in extracted.get("wants", []):
        _bump(profile["preferences"]["wants"], it["id"], key="weight")
        learned.append(it["id"])
    for it in extracted.get("avoids", []):
        if it["id"] not in {x["id"] for x in profile["preferences"]["avoids"]}:
            profile["preferences"]["avoids"].append({"id": it["id"], "weight": 0.7, "source": "stated", "count": 1})
            learned.append(it["id"])
    routed = policy.route_profile(extracted, profile["appearance"]["consent_sensitive"])
    for it in routed["self_described"]:
        if it["id"] not in {x["id"] for x in profile["appearance"]["self_described"]}:
            profile["appearance"]["self_described"].append({"id": it["id"], "source": "self"})
    profile["appearance"]["pending_consent"] = sorted({*profile["appearance"]["pending_consent"],
                                                       *(x["id"] for x in routed["pending_consent"])})
    _cap(p["hobbies"], MAX_HOBBIES)
    _cap(p["traits"], MAX_TRAITS)
    return learned


def merge_values(profile, values: dict, text: str):
    """ผลจาก pipelines.hybrid.values_extract.extract (self / wants) + เก็บประโยคไว้ทำ values_text"""
    v = profile["values"]
    for side, key in (("self", "self_text"), ("wants", "want_text")):
        known = {d: x for d, x in values.get(side, {}).items() if x != "unknown"}
        if known:
            v[side].update(known)
            if text not in v[key]:
                v[key] = (v[key] + [text])[-5:]


def decay(profile, now=None):
    """confidence ลดครึ่งทุก 60 วันที่ไม่ถูกพูดถึง; ต่ำกว่า 0.3 ลบทิ้ง"""
    now = now or time.time()
    for field in ("hobbies", "traits", "comm_style"):
        kept = []
        for x in profile["persona"][field]:
            days = (now - time.mktime(time.strptime(x.get("last_seen", str(date.today())), "%Y-%m-%d"))) / 86400
            c = x["confidence"] * 0.5 ** (max(0, days) / DECAY_HALF_LIFE_DAYS)
            if c >= MIN_CONFIDENCE:
                kept.append({**x, "confidence_now": round(c, 3)})
        profile["persona"][field] = kept


def build_summaries(profile):
    """ข้อความสำหรับ Dense — ไม่มีรูปลักษณ์โดยเจตนา (เหมือน pipelines/mock/summaries.py)"""
    lab = taxonomy.labels()
    appearance = taxonomy.appearance_ids()
    names = lambda xs: ", ".join(lab[x["id"]] for x in xs if x["id"] not in appearance)
    p, d = profile["persona"], profile["demographic"]
    parts = [f"อายุ {d['age']} ปี" if d.get("age") else "", f"คณะ{d['faculty']}" if d.get("faculty") else "",
             f"นิสัย: {names(p['traits'])}" if p["traits"] else "", f"งานอดิเรก: {names(p['hobbies'])}" if p["hobbies"] else "",
             f"การสื่อสาร: {names(p['comm_style'])}" if p["comm_style"] else "", " ".join(profile["values"]["self_text"])]
    wants = [x for x in profile["preferences"]["wants"] if x["id"] not in appearance]
    avoids = [x for x in profile["preferences"]["avoids"] if x["id"] not in appearance]
    profile["summaries"] = {
        "persona_text": " ".join(x for x in parts if x).strip(),
        "preference_text": (f"อยากได้คนที่ {names(wants)} " if wants else "") + " ".join(profile["values"]["want_text"]),
        "avoid_text": f"ไม่ชอบคนที่ {names(avoids)}" if avoids else "",
        "values_text": " ".join(profile["values"]["self_text"]),
        "values_want_text": " ".join(profile["values"]["want_text"]),
    }
    filled = [bool(p["hobbies"]), bool(p["traits"]), bool(wants), bool(d.get("gender")), bool(d.get("age")),
              bool(profile["values"]["self"])]
    profile["profile_completeness"] = round(sum(filled) / len(filled), 2)
    return profile


def ready_to_match(profile) -> bool:
    d = profile["demographic"]
    return bool(profile["consent"]["matching"] and d.get("gender") and d.get("seeking") and d.get("age")
                and (profile["persona"]["hobbies"] or profile["persona"]["traits"] or profile["preferences"]["wants"]))


def describe(profile) -> str:
    """สิ่งที่ระบบจำได้ (ความโปร่งใส: ผู้ใช้ขอดูได้ทุกเมื่อ)"""
    lab = taxonomy.labels()
    names = lambda xs: ", ".join(lab.get(x["id"], x["id"]) for x in xs) or "-"
    p, pr = profile["persona"], profile["preferences"]
    return (f"📋 สิ่งที่ผมจำได้เกี่ยวกับคุณ\n"
            f"• งานอดิเรก: {names(p['hobbies'])}\n• นิสัย: {names(p['traits'])}\n"
            f"• อยากได้คนที่: {names(pr['wants'])}\n• ไม่ชอบคนที่: {names(pr['avoids'])}\n"
            f"• ค่านิยมของคุณ: {profile['summaries'].get('values_text') or '-'}\n"
            f"• ค่านิยมที่อยากได้ในคู่: {profile['summaries'].get('values_want_text') or '-'}\n"
            f"(พิมพ์ \"ลบข้อมูลของฉัน\" เพื่อลบทั้งหมดได้ทุกเมื่อ)")
