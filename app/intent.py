"""แยกเจตนาข้อความ (rule-based อธิบายได้ ไม่เปลือง LLM)

ลำดับ: สถานะที่ค้างอยู่ (onboarding / รอเหตุผลเลิกคุย) > คำสั่ง > คำถามปรึกษา > คุยเล่น
"""
FIND_MATCH = ("หาคู่", "หาคน", "แนะนำคน", "แนะนำคู่", "จับคู่", "match", "หาแฟน")
SHOW_PROFILE = ("โปรไฟล์ของฉัน", "โปรไฟล์ฉัน", "จำอะไรเกี่ยวกับ", "ข้อมูลของฉัน")
DELETE_ME = ("ลบข้อมูลของฉัน", "ลบข้อมูลฉัน", "ลบบัญชี")
UNMATCH = ("เลิกคุย", "ไม่คุยต่อ", "ไม่ไปต่อ")
QUESTION = ("?", "ไหม", "มั้ย", "อย่างไร", "ยังไง", "ทำไง", "ทำยังไง", "คืออะไร", "ควร", "ทำไม", "เป็นไง", "แบบไหน", "ปรึกษา")


def classify(text: str, state: str = "ready") -> str:
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
    if any(k in t for k in QUESTION):
        return "ask_advice"
    return "chat"
