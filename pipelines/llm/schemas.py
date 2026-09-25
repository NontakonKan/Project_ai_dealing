"""JSON schema สำหรับ structured output — enum = รหัสใน taxonomy -> โมเดลตอบรหัสนอก taxonomy ไม่ได้"""
from ..common import taxonomy

# field ที่สกัดจากแชท -> กลุ่ม taxonomy ที่อนุญาต
PROFILE_FIELDS = {
    "hobbies": ["hobbies"],
    "traits": ["traits"],
    "comm_style": ["comm_styles"],
    "self_described": ["body_types", "skin_tones"],             # รูปลักษณ์ที่ผู้พูดบอกเกี่ยวกับตัวเอง
    "wants": ["traits", "body_types", "skin_tones", "hygiene"],  # สเปกที่อยากได้ (รวมรูปลักษณ์)
    "avoids": ["red_flags", "body_types", "skin_tones"],
}
UNMATCH_FIELDS = {
    "red_flags": ["red_flags"],                   # พฤติกรรม -> เก็บที่ผู้พูด + รายงานอีกฝ่าย
    "appearance": ["body_types", "skin_tones"],   # รูปลักษณ์ -> เก็บเป็นสเปกผู้พูดเท่านั้น
    "hygiene": ["hygiene"],
}


def allowed_ids(fields: dict) -> dict:
    return {f: [i for g in groups for i in taxonomy.ids(g)] for f, groups in fields.items()}


def _item(ids, extra=None):
    props = {"id": {"type": "string", "enum": ids}, "evidence": {"type": "string"}, **(extra or {})}
    return {"type": "object", "properties": props, "required": list(props)}


def profile_schema() -> dict:
    allowed = allowed_ids(PROFILE_FIELDS)
    return {"type": "object", "required": list(allowed),
            "properties": {f: {"type": "array", "items": _item(ids)} for f, ids in allowed.items()}}


def unmatch_schema() -> dict:
    allowed = allowed_ids(UNMATCH_FIELDS)
    sev = {"severity": {"type": "number"}}
    return {"type": "object", "required": list(allowed),
            "properties": {f: {"type": "array", "items": _item(ids, sev)} for f, ids in allowed.items()}}
