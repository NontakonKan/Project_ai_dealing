"""Query routing: เลือกเส้นทางตามลักษณะคำถาม (rule-based อธิบายได้)

  ไม่พบ concept ใน taxonomy             -> dense   (คำถามทั่วไป/ข้อเท็จจริงในเอกสาร)
  ถามความเข้ากันได้ หรือพบ >= 2 concept -> graph   (ความสัมพันธ์ระหว่าง concept = จุดแข็งของกราฟ)
  อื่นๆ                                 -> hybrid
chunk หมวดการแพทย์ (RESTRICTED) ใช้ได้เฉพาะคำถามสุขภาพ (HEALTH_CUES)
  วัดจริง: "นัดเพื่อนกับแฟนวันเดียวกัน" ถูก Dense+rerank ดึงเรื่อง "การสื่อสารกับคู่เพศสัมพันธ์" มาอันดับ 5
"""
RESTRICTED = {"sexual_health"}
HEALTH_CUES = ("โรค", "ติดเชื้อ", "เชื้อ", "ถุงยาง", "เอชไอวี", "HIV", "hiv", "เอดส์", "ซิฟิลิส", "หนองใน", "เริม", "หูดหงอนไก่",
               "เพศสัมพันธ์", "มีอะไรกับ", "มีเซ็กส์", "เซ็กส์", "คุมกำเนิด", "ตั้งครรภ์", "STD", "STI", "ตกขาว", "อาการ",
               "ตรวจเลือด", "กินยา", "ใช้ยา", "ยาอะไร", "ยาฆ่าเชื้อ", "ปัสสาวะ", "อวัยวะเพศ")
RELATION_CUES = ("เข้ากับ", "เข้ากัน", "คบกับ", "คบกัน", "ตรงข้าม", "ขัดแย้งกับ", "ไปด้วยกัน", "คู่กับ", "เหมาะกับ")


def route(query: str, concepts: set) -> str:
    if not concepts:
        return "dense"
    if any(c in query for c in RELATION_CUES) or len(concepts) >= 2:
        return "graph"
    return "hybrid"


def is_health(query: str) -> bool:
    return any(c in query for c in HEALTH_CUES)
