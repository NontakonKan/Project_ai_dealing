"""ข้อความตอบกลับแบบคุยเล่น (ซีน 1 ใน req.md) — Local LLM + fallback เมื่อ LLM ล้มเหลว"""
from pipelines.common import taxonomy
from pipelines.llm import ollama_client
from pipelines.llm.config import GenConfig

from .config import CHAT_MODEL, FALLBACK_MODEL

SYSTEM = """คุณคือ "น้องดีล" ผู้ช่วยหาคู่ใน LINE ของนักศึกษา ม.อ. พูดเป็นกันเอง อบอุ่น ใช้ "ผม" และลงท้าย "ครับ"
ตอบสั้น 2-3 ประโยค: (1) เห็นใจ/ร่วมยินดีกับเรื่องที่ผู้ใช้เล่าแบบเจาะจง
(2) ถ้ามี "สิ่งที่เพิ่งจำได้" ต้องพูดถึงอย่างน้อย 1 อย่างตรงๆ เช่น "ชอบทำอาหารกับฟังเพลงชิลนี่ชาร์จพลังดีมากเลยครับ" แล้วบอกว่าจะจำไว้หาคนที่เข้ากัน
ห้ามให้คำแนะนำทางการแพทย์ ห้ามพูดถึงรูปร่างหน้าตาสีผิวของใคร ห้ามแต่งเรื่องเกี่ยวกับผู้ใช้"""
FALLBACK_TEXT = "ขอบคุณที่เล่าให้ฟังนะครับ 😊 ผมจดไว้แล้ว ถ้าอยากให้ช่วยหาคนที่เข้ากัน พิมพ์ \"หาคู่ให้หน่อย\" ได้เลยครับ"


def chat_reply(message, history, learned_ids):
    labels = taxonomy.labels()
    appearance = taxonomy.appearance_ids()
    learned = ", ".join(labels[i] for i in dict.fromkeys(learned_ids) if i in labels and i not in appearance)
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]} for h in history]
    msgs.append({"role": "user", "content": message + (f"\n\n(สิ่งที่เพิ่งจำได้: {learned})" if learned else "")})
    for model in (CHAT_MODEL, FALLBACK_MODEL):
        try:
            return ollama_client.chat(model, msgs, GenConfig(temperature=0.7, num_ctx=4096, num_predict=200)).text.strip()
        except Exception:
            continue
    return FALLBACK_TEXT
