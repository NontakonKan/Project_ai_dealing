"""สร้างโปรไฟล์ผู้ใช้จำลองจาก archetype (persona, preferences, red flags ที่ซ่อนไว้)"""
from datetime import timedelta

from .config import ALL_TRAITS, ARCHETYPES, ATTACH_DIST, FACULTIES, HOBBIES, LOVE_LANGS, NICKNAMES
from .appearance import make_appearance, make_appearance_prefs
from .sampling import conf, pick_weighted
from .values import make_values


def make_user(i, rng, today):
    arch_name = rng.choice(list(ARCHETYPES))
    arch = ARCHETYPES[arch_name]
    gender = rng.choice(["M", "F", "F", "M", "NB"])
    seeking = {"M": ["F"], "F": ["M"], "NB": ["M", "F", "NB"]}[gender]
    if rng.random() < 0.12:
        seeking = ["M", "F", "NB"]

    traits = list(arch["traits"][:2]) + ([arch["traits"][2]] if rng.random() < 0.7 else [])
    extra = [t for t in ALL_TRAITS if t not in traits and not (
        {t, *traits} >= {"trait:introvert", "trait:extrovert"} or {t, *traits} >= {"trait:calm", "trait:emotional"})]
    if rng.random() < 0.6:
        traits.append(rng.choice(extra))
    hobbies = rng.sample(arch["hobbies"], k=min(len(arch["hobbies"]), rng.randint(2, 4)))
    if rng.random() < 0.4:
        hobbies.append(rng.choice([h for h in HOBBIES if h not in hobbies]))

    attach = pick_weighted(rng, ATTACH_DIST)
    comm = ["comm:direct" if ("trait:logical" in traits or rng.random() < 0.4) else "comm:gentle",
            rng.choice(["comm:frequent_texter", "comm:slow_texter"])]

    # red flags ที่ "มีจริง" (ground truth ซ่อนไว้ ระบบจริงมองไม่เห็น ใช้สร้าง event + evaluation)
    hidden_flags = []
    if attach == "attach:avoidant" and rng.random() < 0.6:
        hidden_flags.append("rf:stonewalling")
    if attach == "attach:anxious" and rng.random() < 0.4:
        hidden_flags.append(rng.choice(["rf:possessive", "rf:no_boundaries"]))
    if "trait:emotional" in traits and rng.random() < 0.35:
        hidden_flags.append("rf:hot_temper")
    if arch_name == "social_butterfly" and rng.random() < 0.45:
        hidden_flags.append("rf:friend_priority")
    if rng.random() < 0.12:
        hidden_flags.append(rng.choice(["rf:ghosting", "rf:dishonest", "rf:inconsistent", "rf:gaslighting", "rf:disrespect"]))
    hidden_flags = sorted(set(hidden_flags))

    # สเปก: อิง archetype ตัวเอง + ทฤษฎีความเข้ากันได้
    want_pool = ["trait:calm", "trait:kind", "trait:funny", "trait:responsible", "trait:logical"]
    if "trait:introvert" in traits:
        want_pool += ["trait:introvert", "trait:homebody"]
    if "trait:extrovert" in traits:
        want_pool += ["trait:extrovert", "trait:adventurous"]
    wants = [{"id": w, "weight": conf(rng, 0.5, 1.0)} for w in rng.sample(sorted(set(want_pool)), k=rng.randint(2, 3))]
    base_avoids = rng.sample(["rf:dishonest", "rf:disrespect", "rf:hot_temper", "rf:possessive", "rf:ghosting"], k=rng.randint(0, 2))
    avoids = [{"id": a, "weight": conf(rng, 0.6, 0.9), "source": "stated", "count": 1} for a in base_avoids]

    persona = {
        "hobbies": [{"id": h, "confidence": conf(rng), "evidence_count": rng.randint(1, 5),
                     "last_seen": str(today - timedelta(days=rng.randint(0, 60)))} for h in hobbies],
        "traits": [{"id": t, "confidence": conf(rng, 0.5, 0.9), "evidence_count": rng.randint(1, 4)} for t in traits],
        "lifestyle": {"sleep": rng.choice(arch["sleep"]), "social_energy": arch["social"], "weekend": arch["weekend"]},
        "comm_style": [{"id": c, "confidence": conf(rng, 0.5, 0.85)} for c in comm],
        "attachment_style": {"id": attach, "confidence": conf(rng, 0.4, 0.8)},
        "love_language": [{"id": l, "confidence": conf(rng, 0.4, 0.8)} for l in rng.sample(LOVE_LANGS, k=2)],
        "love_components": {"intimacy": rng.randint(3, 5), "passion": rng.randint(2, 5), "commitment": rng.randint(2, 5)},
        "life_satisfaction": rng.randint(2, 5),
    }
    appearance, appearance_truth = make_appearance(rng)
    app_wants, app_avoids = make_appearance_prefs(rng)
    wants += app_wants
    avoids += app_avoids
    user = {
        "user_id": f"U{i:03d}",
        "display_name": rng.choice(NICKNAMES),
        "demographic": {"age": rng.randint(19, 26), "gender": gender, "seeking": seeking,
                        "faculty": rng.choice(FACULTIES), "campus": "หาดใหญ่"},
        "persona": persona,
        "appearance": appearance,
        "preferences": {"wants": wants, "avoids": avoids, "age_range": [18, 30]},
        "reported_traits": [],
        "summaries": {},
        "consent": {"matching": rng.random() > 0.03, "updated_at": str(today - timedelta(days=rng.randint(0, 90)))},
        "_archetype": arch_name,
        "_ground_truth_flags": hidden_flags,
        "_ground_truth_appearance": appearance_truth,
        "_ground_truth_values": make_values(rng),
    }
    return user
