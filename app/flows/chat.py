"""คุยเล่น (ซีน 1): สกัดบุคลิก/สเปก/ค่านิยม -> merge โปรไฟล์ -> ตอบแบบเพื่อน"""
from pipelines.llm import tasks

from .. import storage
from ..config import HISTORY_TURNS
from ..flex import MENU, postback_quick, text
from ..profile import merge_extraction, merge_values, ready_to_match
from ..replies import chat_reply
from .common import load, save

VALUE_CUES = ("ลูก", "เมือง", "ต่างจังหวัด", "บ้านเกิด", "บ้านสวน", "เงิน", "ออม", "สัตว์", "หมา", "แมว", "ช้อป")
WANT_CUES = ("อยากได้คน", "ชอบคน", "สเปก", "สเป็ค", "หาคน", "อยากเจอคน")


def handle(line_user, msg):
    p = load(line_user)
    before = set(p["appearance"]["pending_consent"])
    try:
        extracted = tasks.extract_profile(msg)["extracted"]
    except Exception:
        extracted = {}
    learned = merge_extraction(p, extracted)
    if any(c in msg for c in VALUE_CUES):
        from pipelines.hybrid.values_extract import extract
        cut = min((msg.find(c) for c in WANT_CUES if c in msg), default=-1)
        parts = {"self": msg[:cut] if cut >= 0 else msg, "wants": msg[cut:] if cut >= 0 else ""}
        for side, part in parts.items():
            if part.strip() and any(c in part for c in VALUE_CUES):
                try:
                    merge_values(p, {side: extract(part, "qwen2.5:latest")}, part.strip())
                except Exception:
                    pass
    save(p)
    history = storage.recent_messages(p["user_id"], HISTORY_TURNS)[:-1]
    out = [text(chat_reply(msg, history, learned), MENU if ready_to_match(p) else None)]
    new_pending = set(p["appearance"]["pending_consent"]) - before
    if new_pending:
        out.append(postback_quick("เรื่องสีผิวเป็นข้อมูลอ่อนไหว ให้ผมใช้ข้อมูลนี้ช่วยจับคู่ได้ไหมครับ? (ไม่ยินยอมก็ใช้งานได้ปกติ)",
                                  [("ยินยอม", "action=sensitive&v=yes"), ("ไม่ใช้ข้อมูลนี้", "action=sensitive&v=no")]))
    return out


def sensitive_consent(line_user, yes: bool):
    p = load(line_user)
    p["appearance"]["consent_sensitive"] = yes
    if yes:
        p["appearance"]["self_described"] += [{"id": i, "source": "self"} for i in p["appearance"]["pending_consent"]]
    p["appearance"]["pending_consent"] = []
    save(p)
    return [text("รับทราบครับ 🙏" + (" จะใช้ข้อมูลนี้เฉพาะตอนจับคู่เท่านั้น" if yes else " ผมจะไม่ใช้ข้อมูลนี้"))]
