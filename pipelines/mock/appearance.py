"""รูปลักษณ์จำลอง: รูปลักษณ์จริง (ซ่อน) / ที่เจ้าตัวระบุเอง / สเปกรูปลักษณ์

- _ground_truth_appearance: ของจริงทุกคน (ระบบมองไม่เห็น) ใช้สร้างเหตุผลเลิกคุย + เฉลย
- appearance.self_described: ส่วนที่เจ้าตัว "เลือกบอก" (สีผิวบอกได้เมื่อ consent_sensitive เท่านั้น)
"""
from .sampling import conf, pick_weighted

BODY_DIST = [("body:slim", 0.30), ("body:average", 0.35), ("body:athletic", 0.15), ("body:curvy", 0.20)]
SKIN_DIST = [("skin:fair", 0.35), ("skin:tan", 0.45), ("skin:dark", 0.20)]
P_DECLARE_BODY, P_CONSENT_SENSITIVE, P_DECLARE_SKIN = 0.7, 0.6, 0.8
P_WANT_BODY, P_WANT_SKIN, P_AVOID_BODY, P_AVOID_SKIN = 0.35, 0.25, 0.2, 0.1


def make_appearance(rng) -> tuple:
    truth = [pick_weighted(rng, BODY_DIST), pick_weighted(rng, SKIN_DIST)]
    consent = rng.random() < P_CONSENT_SENSITIVE
    declared = []
    if rng.random() < P_DECLARE_BODY:
        declared.append({"id": truth[0], "source": "self"})
    if consent and rng.random() < P_DECLARE_SKIN:
        declared.append({"id": truth[1], "source": "self"})
    return {"self_described": declared, "consent_sensitive": consent}, truth


def make_appearance_prefs(rng) -> tuple:
    """คืน (wants, avoids) ด้านรูปลักษณ์ (ไม่ขัดกันเอง)"""
    wants, avoids = [], []
    for p_want, p_avoid, dist in ((P_WANT_BODY, P_AVOID_BODY, BODY_DIST), (P_WANT_SKIN, P_AVOID_SKIN, SKIN_DIST)):
        want = pick_weighted(rng, dist) if rng.random() < p_want else None
        if want:
            wants.append({"id": want, "weight": conf(rng, 0.4, 0.8)})
        if rng.random() < p_avoid:
            avoid = rng.choice([v for v, _ in dist if v != want])
            avoids.append({"id": avoid, "weight": conf(rng, 0.4, 0.8), "source": "stated", "count": 1})
    return wants, avoids
