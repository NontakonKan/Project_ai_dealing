"""ข้อความตอบกลับแบบคุยเล่น (ซีน 1 ใน req.md) — Local LLM + fallback เมื่อ LLM ล้มเหลว"""
import re

from pipelines.common import taxonomy
from pipelines.llm import providers
from pipelines.llm.config import GenConfig

from .config import CHAT_MODEL, FALLBACK_MODEL

SYSTEM = """คุณคือ "น้องดีล" ผู้ช่วยหาคู่ใน LINE ของนักศึกษา มหาวิทยาลัยสงขลานครินทร์ (ม.อ.) พูดเป็นกันเอง อบอุ่น ใช้ "ผม" และลงท้าย "ครับ"
ตอบสั้นๆ 2-3 ประโยคเป็นภาษาพูดธรรมดา ไม่ใส่หัวข้อ ไม่ใส่ตัวเลขนำหน้า

หน้าที่และขอบเขต:
1. ดูแลเรื่องหาคู่ หาเพื่อนคุย และรับฟังความชอบ/สเปก/ชีวิตนักศึกษา ม.อ.
2. กฎเรื่องคำถามนอกเรื่อง (Out-of-Domain Guardrail): หากผู้ใช้ถามคำถามกวน ไร้สาระ ชวนคุยเล่นที่ไม่เกี่ยวกับการหาคู่หรือไลฟ์สไตล์ (เช่น "แมวกับไก่ ตัวอะไรอร่อยกว่า", คำถามเชาวน์, เล่นมุก, เรื่องการเมือง, หรือเรื่องทั่วไป):
   - ห้ามเล่นตามน้ำ ห้ามตอบกวน หรือตอบรับมุกตลกเด็ดขาด
   - ให้ปฏิเสธอย่างสุภาพเป็นกันเอง แล้วดึงบทสนทนากลับมาเรื่องหาคู่ เช่น "เรื่องนี้ผมไม่เชี่ยวชาญเลยครับ 😅 แต่ถ้าเรื่องหาคู่ หาเพื่อนคุย หรือสเปกคนที่ชอบใน ม.อ. ถามผมได้เต็มที่เลยนะ เล่าให้ฟังได้นะครับว่าชอบคนแบบไหน"
3. การตอบรับข้อมูล (สิ่งที่เพิ่งจำได้):
   - แยกให้ชัดเจนระหว่าง "เรื่องของตัวผู้ใช้" กับ "สเปกคนที่ชอบ": ถ้าผู้ใช้เล่าสเปก ให้ตอบรับว่าจำได้ว่า "ชอบคนที่..." ห้ามพูดเสมือนว่าผู้ใช้เป็นคนแบบนั้นเอง
   - ตัวอย่าง: ชอบดูหนังเหมือนกันเลยครับ 😊 แล้วก็จำได้ว่าชอบคนที่อ่านหนังสือและเรียนคณะแพทย์ด้วย เดี๋ยวผมช่วยหาคนที่เคมีเข้ากันให้นะครับ
4. ห้ามให้ความรู้เชิงลึก คำแนะนำ หรือวิธีการใดๆ (โหมดนี้แค่คุยเล่นและจำข้อมูล) ถ้าผู้ใช้อยากได้คำแนะนำความสัมพันธ์ ให้ชวนกดปุ่ม "💬 ปรึกษาเรื่องความรัก" แทน
5. ห้ามให้คำแนะนำทางการแพทย์ ห้ามพูดถึงรูปร่างหน้าตาสีผิวหรือศาสนาของใคร ห้ามแต่งเรื่องเกี่ยวกับผู้ใช้"""
# รูปแบบของโหมดปรึกษา/ข้อความภายใน ที่ต้องไม่โผล่ในคุยเล่น (LLM ชอบเลียนแบบจากประวัติแชทแล้วแต่งแหล่งอ้างอิงปลอม)
RE_REFS = re.compile(r"\n*📚[^\n]*|\s*\[\d+(?:\s*,\s*\d+)*\]|\n*\(สิ่งที่เพิ่งจำได้[^)]*\)")


def _clean(t: str) -> str:
    return RE_REFS.sub("", t).strip()
FALLBACK_TEXT = "ขอบคุณที่เล่าให้ฟังนะครับ 😊 ผมจดไว้แล้ว ถ้าอยากให้ช่วยหาคนที่เข้ากัน พิมพ์ \"หาคู่ให้หน่อย\" ได้เลยครับ"


def format_learned(learned_ids):
    labels = taxonomy.labels()
    appearance = taxonomy.appearance_ids()
    self_items, wants_items = [], []
    for i in dict.fromkeys(learned_ids):
        if i in appearance:
            continue
        if i.startswith("wants:"):
            tid = i[6:]
            if tid not in appearance and tid in labels:
                wants_items.append(labels[tid])
            elif tid not in appearance:
                wants_items.append(tid)
        elif i.startswith("อยากได้คนเรียนคณะ"):
            wants_items.append(i)
        elif i in labels:
            self_items.append(labels[i])
        elif ":" not in i or " " in i:
            if "อยากได้" in i or "ชอบคน" in i:
                wants_items.append(i)
            else:
                self_items.append(i)

    parts = []
    if self_items:
        parts.append(f"ความชอบส่วนตัวของผู้ใช้: {', '.join(self_items)}")
    if wants_items:
        parts.append(f"สเปกคู่ที่ชอบ: {', '.join(wants_items)}")
    return " | ".join(parts)


def chat_reply(message, history, learned_ids):
    learned = format_learned(learned_ids)
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": "user" if h["role"] == "user" else "assistant", "content": _clean(h["text"])} for h in history]
    msgs.append({"role": "user", "content": message + (f"\n\n(สิ่งที่เพิ่งจำได้: {learned})" if learned else "")})
    try:
        reply = providers.chat(CHAT_MODEL, msgs, GenConfig(temperature=0.7, num_ctx=4096, num_predict=200),
                              fallback=FALLBACK_MODEL).text.strip()
        return _clean(re.sub(r"^\s*\(?\d\)\s*", "", reply, flags=re.M)) or FALLBACK_TEXT   # กันเลขข้อ/อ้างอิงหลุด
    except Exception:
        return FALLBACK_TEXT
