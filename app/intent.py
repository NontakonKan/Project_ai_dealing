"""แยกเจตนาข้อความ

ลำดับ: สถานะที่ค้างอยู่ (onboarding / รอเหตุผลเลิกคุย / รอ LINE ID) > เจตนาจากความหมาย (app/intent_model.py)
คำสั่งและคำถามไม่ใช้การดักคำตายตัวแล้ว: SBERT + BM25 + LLM เมื่อก้ำกึ่ง
วัดจริงชุดสด 26 ประโยค (python -m app.intent_eval --fresh): กฎคำตายตัว 50% -> 100%
"""
LAST = {}   # การตัดสินล่าสุด (เจตนาอันดับต้น + ตัดสินด้วยอะไร) ไว้เขียน log


FOLLOWUP = ("ยกตัวอย่าง", "ขอรายละเอียด", "อธิบายเพิ่ม", "ขยายความ", "ข้อแรก", "ข้อสอง", "ข้อสาม",
            "ข้อที่", "เมื่อกี้", "ที่บอก", "แบบเดิม", "แบบนั้น", "แบบนี้", "เรื่องนี้", "เรื่องเดิม", "กับเขา", "กับเธอ", "คนเดิม", "ทำตามแล้ว", "ลองแล้ว")
TOPIC_RESET = ("เปลี่ยนเรื่อง", "เรื่องใหม่", "ถามเรื่องอื่น")


CONTINUE_PREFIX = ("แล้วถ้า", "แล้วควร", "แล้วเขา", "แล้วต้อง")
PRONOUN_PREFIX = ("เขา", "เธอ")


def is_followup(text):
    t = text.strip().lower()
    return not any(c in t for c in TOPIC_RESET) and (
        any(c in t for c in FOLLOWUP) or t.startswith(CONTINUE_PREFIX + PRONOUN_PREFIX))


def needs_context(text):
    """ต้องมีบทสนทนาก่อนหน้าจึงเข้าใจได้ ("ข้อสองล่ะ", "แล้วควรทำยังไง")
    ต่างจากคำถามที่แค่ขึ้นต้นด้วย เขา/เธอ ("เขาไม่ตอบแชท ทำไงดี") ซึ่งถามครั้งแรกได้โดยไม่ต้องมีประวัติ"""
    t = text.strip().lower()
    return any(c in t for c in FOLLOWUP) or t.startswith(CONTINUE_PREFIX)


def classify(text: str, state: str = "ready", history=None) -> str:
    t = text.strip().lower()
    if state.startswith("onboard"):
        return "onboarding"
    if state == "await_unmatch_reason":
        return "unmatch_reason"
    if state == "await_contact":
        return "contact"
    from .intent_model import ROUTE, classify as by_meaning
    kind, info = by_meaning(text.strip())
    LAST.clear()
    LAST.update(info, raw=kind)
    return ROUTE.get(kind, kind)
