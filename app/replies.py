"""ข้อความตอบกลับแบบคุยเล่น (ซีน 1 ใน req.md) — Local LLM + fallback เมื่อ LLM ล้มเหลว"""
import re

from pipelines.common import taxonomy
from pipelines.llm import providers
from pipelines.llm.config import GenConfig

from .config import CHAT_MODEL, FALLBACK_MODEL

SYSTEM = """คุณคือ "น้องดีล" ผู้ช่วยหาคู่ใน LINE ของนักศึกษา ม.อ. พูดเป็นกันเอง อบอุ่น ใช้ "ผม" และลงท้าย "ครับ"
ตอบสั้นๆ 2-3 ประโยคเป็นภาษาพูดธรรมดา ไม่ใส่หัวข้อ ไม่ใส่ตัวเลขนำหน้า
เริ่มจากตอบรับเรื่องที่ผู้ใช้เล่าแบบเจาะจง ถ้ามี "สิ่งที่เพิ่งจำได้" ให้พูดถึงอย่างน้อย 1 อย่างตรงๆ แล้วบอกว่าจะจำไว้หาคนที่เข้ากัน
ตัวอย่างคำตอบ: ชอบทำอาหารกับฟังเพลงชิลนี่ชาร์จพลังดีมากเลยครับ 😊 ผมจำไว้แล้ว จะหาคนที่ชอบอะไรคล้ายๆ กันให้นะครับ
ห้ามให้คำแนะนำทางการแพทย์ ห้ามพูดถึงรูปร่างหน้าตาสีผิวหรือศาสนาของใคร ห้ามแต่งเรื่องเกี่ยวกับผู้ใช้"""
FALLBACK_TEXT = "ขอบคุณที่เล่าให้ฟังนะครับ 😊 ผมจดไว้แล้ว ถ้าอยากให้ช่วยหาคนที่เข้ากัน พิมพ์ \"หาคู่ให้หน่อย\" ได้เลยครับ"


def chat_reply(message, history, learned_ids):
    labels = taxonomy.labels()
    appearance = taxonomy.appearance_ids()
    # รหัส taxonomy -> ชื่อไทย / ข้อความธรรมดา (เช่น "อยากได้คนเรียนคณะวิศวกรรมศาสตร์") ใช้ตามนั้น
    learned = ", ".join(labels.get(i) or i for i in dict.fromkeys(learned_ids)
                        if i not in appearance and (i in labels or ":" not in i))
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]} for h in history]
    msgs.append({"role": "user", "content": message + (f"\n\n(สิ่งที่เพิ่งจำได้: {learned})" if learned else "")})
    try:
        reply = providers.chat(CHAT_MODEL, msgs, GenConfig(temperature=0.7, num_ctx=4096, num_predict=200),
                              fallback=FALLBACK_MODEL).text.strip()
        return re.sub(r"^\s*\(?\d\)\s*", "", reply, flags=re.M).strip() or FALLBACK_TEXT   # กันเลขข้อจาก prompt หลุด
    except Exception:
        return FALLBACK_TEXT
