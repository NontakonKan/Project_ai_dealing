"""กติกาว่าข้อมูลแต่ละหมวดไปเก็บที่ไหน (เขียนเป็นโค้ด -> ตรวจสอบได้ ไม่ให้ LLM ตัดสินเอง)

| หมวด          | ผู้พูด (A)            | ผู้ถูกพูดถึง (B)                   |
| red_flags     | avoids (สะสมน้ำหนัก)   | reported_traits (ใช้ได้เมื่อ >= 3 คน) |
| body / skin   | avoids / wants         | ไม่เก็บ (B ต้องระบุเองเท่านั้น)       |
| hygiene       | wants (ดูแลตัวเอง)     | ไม่เก็บ                            |
"""
from ..common import taxonomy

REPORT_THRESHOLD = 3
DEFAULT_SEVERITY = 0.6


def _groups_allowed_on_target():
    return set(taxonomy.appearance_policy()["reported_traits_groups"])


def route_unmatch(extracted: dict) -> dict:
    """extracted จาก extract_unmatch -> {"speaker_avoids", "speaker_wants", "report_target"}"""
    on_target = _groups_allowed_on_target()
    avoids, wants, report = [], [], []
    for field in ("red_flags", "appearance"):
        for it in extracted.get(field, []):
            item = {"id": it["id"], "severity": float(it.get("severity") or DEFAULT_SEVERITY)}
            avoids.append(item)
            if taxonomy.group_of(it["id"]) in on_target:
                report.append(item)
    for it in extracted.get("hygiene", []):
        wants.append({"id": it["id"], "severity": float(it.get("severity") or DEFAULT_SEVERITY)})
    return {"speaker_avoids": avoids, "speaker_wants": wants, "report_target": report}


def route_profile(extracted: dict, consent_sensitive: bool) -> dict:
    """extracted จาก extract_profile -> อะไรเก็บได้ (self_described สีผิวต้องมี consent ข้อมูลอ่อนไหว)"""
    sensitive = {t["id"] for t in taxonomy.load()["skin_tones"]}
    kept, pending = [], []
    for it in extracted.get("self_described", []):
        (kept if consent_sensitive or it["id"] not in sensitive else pending).append(it)
    return {**extracted, "self_described": kept, "pending_consent": pending}


def appearance_score(speaker: dict, candidate: dict) -> float:
    """คะแนนเสริมรูปลักษณ์ในอันดับของ speaker (-1..1) x w_appearance — ใช้ข้อมูลที่ candidate ระบุเองเท่านั้น"""
    appearance = taxonomy.appearance_ids()
    declared = {x["id"] for x in candidate.get("appearance", {}).get("self_described", [])}
    if not declared:
        return 0.0
    wants = {x["id"]: x["weight"] for x in speaker["preferences"]["wants"] if x["id"] in appearance}
    avoids = {x["id"]: x["weight"] for x in speaker["preferences"]["avoids"] if x["id"] in appearance}
    s = sum(w for i, w in wants.items() if i in declared) - sum(w for i, w in avoids.items() if i in declared)
    return max(-1.0, min(1.0, s)) * taxonomy.appearance_policy()["w_appearance"]
