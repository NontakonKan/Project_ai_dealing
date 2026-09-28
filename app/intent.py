"""แยกเจตนาข้อความ (rule-based อธิบายได้ ไม่เปลือง LLM)

ลำดับ: สถานะที่ค้างอยู่ (onboarding / รอเหตุผลเลิกคุย) > คำสั่ง > คำถามปรึกษา > คุยเล่น
"""
FIND_MATCH = ("หาคู่", "หาคน", "แนะนำคน", "แนะนำคู่", "จับคู่", "match", "หาแฟน")
SHOW_PROFILE = ("โปรไฟล์ของฉัน", "โปรไฟล์ฉัน", "จำอะไรเกี่ยวกับ", "ข้อมูลของฉัน")
DELETE_ME = ("ลบข้อมูลของฉัน", "ลบข้อมูลฉัน", "ลบบัญชี")
UNMATCH = ("เลิกคุย", "ไม่คุยต่อ", "ไม่ไปต่อ")
QUESTION = ("?", "ไหม", "มั้ย", "อย่างไร", "ยังไง", "ทำไง", "ทำยังไง", "คืออะไร", "ควร", "ทำไม", "เป็นไง", "แบบไหน", "ปรึกษา",
            "ได้ไง", "ได้ยังไง", "จะรู้", "รู้ได้", "หรือเปล่า", "รึเปล่า", "เปล่า?", "ดีไหม", "ดีมั้ย", "ยังไงดี", "ไงดี",
            "แนะนำหน่อย", "ขอคำแนะนำ", "ขอวิธี", "มีวิธี", "เทคนิค", "สอนหน่อย", "อะไรบ้าง", "เท่าไร", "เท่าไหร่", "กี่",
            "อะไรดี", "วิธี", "ดูยังไง", "ดูไง", "ยังไงให้", "เหรอ", "หรอ", "ได้มั้ย", "ได้ไหม")


FOLLOWUP = ("ยกตัวอย่าง", "ขอรายละเอียด", "อธิบายเพิ่ม", "ขยายความ", "ข้อแรก", "ข้อสอง", "ข้อสาม",
            "ข้อที่", "เมื่อกี้", "ที่บอก", "แบบเดิม", "แบบนั้น", "แบบนี้", "เรื่องนี้", "เรื่องเดิม", "กับเขา", "กับเธอ", "คนเดิม", "ทำตามแล้ว", "ลองแล้ว")
TOPIC_RESET = ("เปลี่ยนเรื่อง", "เรื่องใหม่", "ถามเรื่องอื่น")


def is_followup(text):
    t = text.strip().lower()
    return not any(c in t for c in TOPIC_RESET) and (
        any(c in t for c in FOLLOWUP) or t.startswith(("แล้วถ้า", "แล้วควร", "แล้วเขา", "แล้วต้อง", "เขา", "เธอ")))


def classify(text: str, state: str = "ready", history=None) -> str:
    t = text.strip().lower()
    if state.startswith("onboard"):
        return "onboarding"
    if state == "await_unmatch_reason":
        return "unmatch_reason"
    if state == "await_contact":
        return "contact"
    if any(k in t for k in DELETE_ME):
        return "delete_me"
    if any(k in t for k in SHOW_PROFILE):
        return "show_profile"
    if any(k in t for k in FIND_MATCH):
        return "find_match"
    if any(k in t for k in UNMATCH):
        return "unmatch"
    from .conversation import wants_recall
    if wants_recall(t):
        return "recall_memory"
    if history and is_followup(t):
        return "ask_advice"
    if any(k in t for k in QUESTION):
        return "ask_advice"
    return "chat"
