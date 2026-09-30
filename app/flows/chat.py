"""คุยเล่น (ซีน 1): สกัดบุคลิก/สเปก/ค่านิยม -> merge โปรไฟล์ -> ตอบแบบเพื่อน"""
import re
from concurrent.futures import ThreadPoolExecutor
from pipelines.llm import tasks
from pipelines.profile import faculty

from .. import storage
from ..config import HISTORY_TURNS
from ..flex import MENU, postback_quick, text
from ..profile import merge_extraction, merge_faculty, merge_values, ready_to_match, set_sensitive_consent
from ..replies import chat_reply
from .common import load, save

VALUE_CUES = ("ลูก", "เมือง", "ต่างจังหวัด", "บ้านเกิด", "บ้านสวน", "เงิน", "ออม", "สัตว์", "หมา", "แมว", "ช้อป",
              "จริงจัง", "ดูใจ", "เพื่อนคุย", "ระยะยาว", "รักจริง", "ครอบครัว", "แต่งงาน", "คบยาว", "เหล้า", "เบียร์", "ดื่ม", "บุหรี่", "พอต", "สูบ",
              "เวลาส่วนตัว", "ตัวติด", "เจอกันทุกวัน", "เจอกันบ่อย", "โพสต์", "ลงรูป", "โซเชียล", "ไอจี",
              "ศาสนา", "พุทธ", "มุสลิม", "อิสลาม", "คริสต์", "ฮาลาล", "มังสวิรัติ", "กินเจ", "วีแกน")
WANT_CUES = ("อยากได้คน", "ชอบคน", "สเปก", "สเป็ค", "หาคน", "อยากเจอคน", "อยากได้แฟน", "อยากได้ผู้", "ชอบผู้",
             "ไม่เอาคน", "ขอคน", "ต้องเป็นคน")
# คำที่เป็นเรื่อง "ค่านิยม" ล้วนๆ: LLM สกัดบุคลิกชอบเดาเป็นนิสัยใกล้เคียง (ไม่สูบ -> รักสะอาด, มุสลิม -> ...) -> ให้ values_extract จัดการแทน
VALUE_ONLY = ("เหล้า", "เบียร์", "ดื่ม", "บุหรี่", "พอต", "สูบ", "ศาสนา", "พุทธ", "มุสลิม", "อิสลาม", "คริสต์",
              "ฮาลาล", "มังสวิรัติ", "กินเจ", "วีแกน", "โพสต์", "ลงรูป", "โซเชียล", "จริงจัง", "ดูใจ",
              "รักจริง", "ครอบครัว", "แต่งงาน")
SENSITIVE_ASK = ("เรื่องศาสนา/อาหาร (เช่น ฮาลาล) เป็นข้อมูลอ่อนไหว 🔒 ให้ผมใช้ข้อมูลนี้ช่วยจับคู่ได้ไหมครับ?\n"
                 "จะใช้เฉพาะตอนคำนวณคู่ ไม่แสดงบนการ์ดหรือบอกใคร (ไม่ยินยอมก็ใช้งานได้ปกติ)")


QUESTION_CUES = ("อะไร", "กว่า", "ไหม", "มั้ย", "หรือเปล่า", "ตัวไหน", "ทำไม", "ยังไง", "อย่างไร")
ADVICE_CUES = ("ทำไม", "ยังไง", "อย่างไร", "ควร", "ไหม", "มั้ย", "ปรึกษา", "วิธี", "ทำไง")


def _extract_text_avoids(text: str) -> list:
    """สกัดสิ่งที่ผู้ใช้บอกว่าไม่ชอบโดยตรงจากข้อความ เพื่อบันทึกเป็นสเปกหลีกเลี่ยง"""
    negative_patterns = [
        r"(?:ไม่ชอบ|ไม่เอา|เกลียด|รับไม่ได้กับ|ไม่โอเคกับ)\s*(?:คน(?:ที่)?)?\s*([^\s,.;]+(?: [^\s,.;]+)?)",
    ]
    custom = []
    for pat in negative_patterns:
        for m in re.finditer(pat, text):
            val = m.group(1).strip()
            val = re.sub(r"(?:ครับ|ค่ะ|จ้า|นะ|เลย|มากๆ|มาก)$", "", val).strip()
            if val and len(val) >= 2 and val not in ("อะไร", "ใคร", "ไหน", "ไหม", "ทำไม", "ยังไง"):
                custom.append(val)
    return custom


def handle(line_user, msg):
    p = load(line_user)
    before = set(p["appearance"]["pending_consent"])

    # ตรวจสอบการทักทายล้วนๆ
    is_greeting = any(w in msg.lower() for w in ["หวัดดี", "สวัสดี", "ดีครับ", "ดีค่ะ", "hello", "hi", "hey"])
    if is_greeting and len(msg.strip()) <= 15 and not any(k in msg for k in ["ชอบ", "อยาก", "ไม่ชอบ", "หาคู่", "ปรึกษา"]):
        greeting_text = (
            f"สวัสดีครับคุณ {p.get('display_name') or ''}! 😊 ผมเป็นบอทหาคู่และที่ปรึกษาความรักของชาว ม.อ. 💙\n\n"
            "วันนี้อยากให้ผมช่วยหาคนคุย เล่าสเปก หรือมีเรื่องความรักความสัมพันธ์อยากปรึกษา พิมพ์บอกผมได้เลยนะครับ!"
        )
        return [text(greeting_text, MENU if ready_to_match(p) else None)]

    # ตรวจสอบคำถามเกี่ยวกับชื่อของตนเอง
    if any(q in msg for q in ["ผมชื่ออะไร", "กระผมชื่ออะไร", "ฉันชื่ออะไร", "หนูชื่ออะไร", "เราชื่ออะไร", "จำชื่อผมได้ไหม"]):
        dname = p.get("display_name") or line_user.get("display_name") or "คุณ"
        return [text(f"คุณคือคุณ '{dname}' ครับ 😊\n\nสามารถพิมพ์ 'โปรไฟล์ของฉัน' เพื่อดูข้อมูลที่ผมจำได้ทั้งหมด หรือพิมพ์บอกข้อมูลเพิ่มเติมได้เลยนะครับ!", MENU if ready_to_match(p) else None)]

    try:
        extracted = tasks.extract_profile(msg)["extracted"]
    except Exception:
        extracted = {}
    fac = faculty.parse(msg)
    # ประโยคเรื่องคณะ/ค่านิยม -> ไม่ให้ LLM เดานิสัยจากคำนั้น (วิศวะ -> มีเหตุผล, ไม่สูบ -> รักสะอาด)
    skip = tuple(fac["spans"]) + VALUE_ONLY
    for field in ("hobbies", "traits", "comm_style", "wants", "avoids"):
        extracted[field] = [x for x in extracted.get(field, []) if not any(w in x.get("evidence", "") for w in skip)]

    # สกัดสิ่งที่ไม่ชอบจากบริบทคำพูดโดยตรง (เช่น "ไม่ชอบคนที่ชื่อเมษ")
    for ca in _extract_text_avoids(msg):
        if not any(ca in x.get("evidence", "") or ca in x.get("id", "") for x in extracted.get("avoids", [])):
            extracted.setdefault("avoids", []).append({"id": f"custom:{ca}", "name": ca, "evidence": ca})

    learned = merge_extraction(p, extracted, msg)
    new_fac = merge_faculty(p, fac, msg)
    history = storage.recent_messages(p["user_id"], HISTORY_TURNS)[:-1]

    # ถ้าผู้ใช้ถามคำถามในแชทแต่ไม่มีข้อมูลโปรไฟล์ ให้ส่งไปค้น RAG ทันที (ไม่คุยเล่นเอง)
    if any(c in msg for c in ADVICE_CUES) and not (learned or new_fac):
        from . import advice
        return advice.handle(line_user, msg, history=history)

    # แยกสิ่งที่จำได้ส่งให้แชทบอตพูดถึงอย่างถูกต้อง (ตัวเอง vs สเปกคู่)
    learned_tags = []
    for f in ("hobbies", "traits", "comm_style"):
        for it in extracted.get(f, []):
            learned_tags.append(it["id"])
    for it in extracted.get("wants", []):
        learned_tags.append(f"wants:{it['id']}")
    for it in extracted.get("avoids", []):
        learned_tags.append(f"ไม่ชอบคนที่:{it.get('name', it['id'].replace('custom:', ''))}")
    for f in new_fac:
        learned_tags.append(f"อยากได้คนเรียนคณะ{f}")

    with ThreadPoolExecutor(max_workers=2) as pool:           # 2 งานนี้ไม่ขึ้นต่อกัน -> ทำพร้อมกัน
        reply_job = pool.submit(chat_reply, msg, history, learned_tags if (learned_tags or new_fac) else learned)
        values_job = pool.submit(_read_values, msg)
        reply, values = reply_job.result(), values_job.result()

    # ถ้าไม่มีข้อมูลโปรไฟล์และไม่ได้เล่าสเปก ให้เตือนขอบเขตงานอย่างสุภาพ ไม่ตอบกวน/เล่นมุก
    if not (learned or new_fac or values) and any(q in msg for q in QUESTION_CUES):
        reply = ("เรื่องนี้ผมไม่มีข้อมูลและไม่สามารถตอบได้ครับ 😅 ผมเป็นผู้ช่วยหาคู่และให้คำปรึกษาเรื่องความสัมพันธ์สำหรับนักศึกษา ม.อ. เท่านั้นครับ\n\n"
                 "สามารถเล่าสเปกคนที่ชอบ ปรึกษาปัญหาความรัก หรือพิมพ์ \"หาคู่ให้หน่อย\" ได้เลยนะครับ!")

    ask_sensitive = False
    for side, part, v in values:
        ask_sensitive |= merge_values(p, {side: v}, part)
    save(p)
    from .. import log
    log.note("จำได้: " + (", ".join(dict.fromkeys(learned)) if learned else "-"))
    if new_fac:
        log.note(f"คณะที่อยากได้: {', '.join(new_fac)}")
    if values:   # ไม่ log ค่าที่อ่อนไหว
        log.note("ค่านิยม: " + ", ".join(f"{side}.{d}" for side, _, v in values for d, x in v.items() if x != "unknown"))
    out = [text(reply, MENU if ready_to_match(p) else None)]
    new_pending = set(p["appearance"]["pending_consent"]) - before
    if new_pending:
        out.append(postback_quick("เรื่องสีผิวเป็นข้อมูลอ่อนไหว ให้ผมใช้ข้อมูลนี้ช่วยจับคู่ได้ไหมครับ? (ไม่ยินยอมก็ใช้งานได้ปกติ)",
                                  [("ยินยอม", "action=sensitive&v=yes"), ("ไม่ใช้ข้อมูลนี้", "action=sensitive&v=no")]))
    if ask_sensitive:
        out.append(postback_quick(SENSITIVE_ASK, [("ยินยอม", "action=sensitive_values&v=yes"),
                                                  ("ไม่ใช้ข้อมูลนี้", "action=sensitive_values&v=no")]))
    return out


def _read_values(msg):
    """แยกประโยคเรื่องตัวเอง / สเปก แล้วให้ LLM อ่านค่านิยม (ใช้เฉพาะข้อความที่มีคำเกี่ยวกับค่านิยม และไม่ใช่คำถาม)"""
    if any(q in msg for q in QUESTION_CUES) or not any(c in msg for c in VALUE_CUES):
        return []
    from pipelines.hybrid.values_extract import extract
    cut = min((msg.find(c) for c in WANT_CUES if c in msg), default=-1)
    parts = {"self": msg[:cut] if cut >= 0 else msg, "wants": msg[cut:] if cut >= 0 else ""}
    out = []
    for side, part in parts.items():
        if part.strip() and any(c in part for c in VALUE_CUES):
            try:
                out.append((side, part.strip(), extract(part, "qwen2.5:latest")))
            except Exception:
                pass
    return out


def sensitive_consent(line_user, yes: bool):
    p = load(line_user)
    p["appearance"]["consent_sensitive"] = yes
    if yes:
        p["appearance"]["self_described"] += [{"id": i, "source": "self"} for i in p["appearance"]["pending_consent"]]
    p["appearance"]["pending_consent"] = []
    save(p)
    return [text("รับทราบครับ 🙏" + (" จะใช้ข้อมูลนี้เฉพาะตอนจับคู่เท่านั้น" if yes else " ผมจะไม่ใช้ข้อมูลนี้"))]


def sensitive_values_consent(line_user, yes: bool):
    p = load(line_user)
    set_sensitive_consent(p, yes)
    save(p)
    return [text("รับทราบครับ 🙏" + (" จะใช้เรื่องศาสนา/อาหารเฉพาะตอนจับคู่ ไม่แสดงให้ใครเห็น" if yes
                                     else " ผมจะไม่เก็บและไม่ใช้เรื่องศาสนา/อาหาร"))]
