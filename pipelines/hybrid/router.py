"""Query routing: เลือกเส้นทางตามลักษณะคำถาม (rule-based อธิบายได้)

  ไม่พบ concept ใน taxonomy             -> dense   (คำถามทั่วไป/ข้อเท็จจริงในเอกสาร)
  ถามความเข้ากันได้ หรือพบ >= 2 concept -> graph   (ความสัมพันธ์ระหว่าง concept = จุดแข็งของกราฟ)
  อื่นๆ                                 -> hybrid
"""
RELATION_CUES = ("เข้ากับ", "เข้ากัน", "คบกับ", "คบกัน", "ตรงข้าม", "ขัดแย้งกับ", "ไปด้วยกัน", "คู่กับ", "เหมาะกับ")


def route(query: str, concepts: set) -> str:
    if not concepts:
        return "dense"
    if any(c in query for c in RELATION_CUES) or len(concepts) >= 2:
        return "graph"
    return "hybrid"
