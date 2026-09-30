"""Explicit ontology shared by validation, export and Neo4j import."""

FORMAT_VERSION = 1
DATASET = "psu_dealing_mock"
GROUP_LABELS = {
    "hobbies": "Hobby", "traits": "Trait", "comm_styles": "CommStyle",
    "attachment_styles": "Attachment", "love_languages": "LoveLanguage",
    "love_components": "LoveComponent", "red_flags": "RedFlag",
    "research_factors": "ResearchFactor",
    # รูปลักษณ์ = สเปกส่วนตัว (appearance_policy ใน taxonomy): ข้อมูลของผู้สมัครมาจาก SELF_DESCRIBED เท่านั้น
    "body_types": "BodyType", "skin_tones": "SkinTone", "hygiene": "Hygiene",
}
APPEARANCE_LABELS = {"BodyType", "SkinTone", "Hygiene"}
CONCEPT_LABELS = set(GROUP_LABELS.values())
FEATURE_LABELS = {"Trait", "CommStyle", "Attachment"}
LABELS = CONCEPT_LABELS | {"User", "Source", "BookChunk", "Claim"}
CLAIM_PREDICATES = {
    "associated_with": "สัมพันธ์กับ",
    "increases": "เพิ่ม",
    "decreases": "ลด",
    "predicts": "ทำนาย",
    "causes": "ก่อให้เกิด",
    "prevents": "ป้องกัน",
    "differs_from": "แตกต่างจาก",
    "part_of": "เป็นส่วนหนึ่งของ",
    "characterized_by": "มีลักษณะเป็น",
    "depends_on": "ขึ้นอยู่กับ",
    "supports": "สนับสนุน",
    "opposes": "ขัดแย้งกับ",
}
CLAIM_PREDICATE_GUIDANCE = {
    "associated_with": "พบความสัมพันธ์ร่วมกัน ห้ามสรุปว่าเป็นเหตุและผล",
    "increases": "ทำให้หรือสัมพันธ์กับการเพิ่มขึ้น ตามถ้อยคำต้นฉบับ",
    "decreases": "ทำให้หรือสัมพันธ์กับการลดลง ตามถ้อยคำต้นฉบับ",
    "predicts": "ใช้เมื่อข้อความระบุการทำนายหรือพยากรณ์โดยตรง",
    "causes": "ใช้เมื่อข้อความระบุเหตุและผลโดยตรงเท่านั้น ไม่ใช้แทน associated_with",
    "prevents": "ยับยั้งหรือป้องกันผลที่ระบุไว้อย่างชัดเจน",
    "differs_from": "มีความแตกต่างเมื่อข้อความเปรียบเทียบโดยตรง",
    "part_of": "เป็นองค์ประกอบหรือส่วนหนึ่งของสิ่งที่ระบุ",
    "characterized_by": "subject มีลักษณะหรือพฤติกรรมตาม object",
    "depends_on": "ผลหรือความสัมพันธ์ขึ้นกับเงื่อนไขที่ระบุ",
    "supports": "หลักฐานสนับสนุนข้อเสนอที่ระบุโดยตรง",
    "opposes": "ข้อความระบุการคัดค้านหรือความขัดแย้งโดยตรง",
}
CLAIM_POLARITIES = {
    "affirmed": "ยืนยันตามข้อความ",
    "negated": "ปฏิเสธตามข้อความ",
    "uncertain": "ยังไม่แน่ชัดตามข้อความ",
}
# Domain/range checks are application-side; Neo4j uniqueness alone is insufficient.
RELATIONS = {
    "HAS_TRAIT": ({"User"}, FEATURE_LABELS),
    "LIKES": ({"User"}, {"Hobby"}),
    "HAS_LOVE_LANGUAGE": ({"User"}, {"LoveLanguage"}),
    "HAS_LOVE_COMPONENT": ({"User"}, {"LoveComponent"}),
    "HAS_FACTOR": ({"User"}, {"ResearchFactor"}),
    "PREFERS": ({"User"}, {"Trait"} | APPEARANCE_LABELS),
    "AVOIDS": ({"User"}, {"RedFlag", "BodyType", "SkinTone"}),
    "REPORTED_AS": ({"User"}, {"RedFlag"}),                 # รายงานจากคนอื่นเป็นพฤติกรรมเท่านั้น ไม่มีรูปลักษณ์
    "SELF_DESCRIBED": ({"User"}, {"BodyType", "SkinTone"}),  # เจ้าตัวระบุเอง (สีผิวต้องมี consent_sensitive)
    "UNMATCHED": ({"User"}, {"User"}),
    "MATCHED": ({"User"}, {"User"}),
    "PASSED": ({"User"}, {"User"}),
    "COMPATIBLE_WITH": (CONCEPT_LABELS, CONCEPT_LABELS),
    "CONFLICTS_WITH": (CONCEPT_LABELS, CONCEPT_LABELS),
    "OPPOSITE_OF": (CONCEPT_LABELS, CONCEPT_LABELS),
    "HAS_CHUNK": ({"Source"}, {"BookChunk"}),
    "NEXT_CHUNK": ({"BookChunk"}, {"BookChunk"}),
    "ABOUT": ({"BookChunk", "Claim"}, CONCEPT_LABELS),
    "SUPPORTED_BY": ({"Claim"}, {"BookChunk"}),
    "SUBJECT": ({"Claim"}, CONCEPT_LABELS),
    "OBJECT": ({"Claim"}, CONCEPT_LABELS),
}
EVENT_RELATIONS = {"unmatch": "UNMATCHED", "matched": "MATCHED", "pass": "PASSED"}
RULE_RELATIONS = {"COMPATIBLE_WITH", "CONFLICTS_WITH", "OPPOSITE_OF"}


def pick(obj, keys):
    """Use allowlists instead of copying arbitrary input properties."""
    return {key: obj[key] for key in keys if key in obj and obj[key] is not None}
