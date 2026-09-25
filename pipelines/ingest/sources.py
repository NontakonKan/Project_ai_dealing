"""ทะเบียนเอกสารต้นทาง + กติกาเฉพาะของแต่ละไฟล์ (config-driven ไม่ hardcode ใน logic)"""
from ..common.paths import DATA

SOURCES = [
    {
        "source_id": "research_cu2561",
        "file": DATA / "งานวิจัยการหาคู่.pdf",
        "doc_type": "research",
        "title": "ความพึงพอใจในความสัมพันธ์แบบคู่รักและปัจจัยที่เกี่ยวข้องของนิสิตจุฬาลงกรณ์มหาวิทยาลัย",
        "year": 2018,
        # บรรทัดที่เป็น header/footer/เลขหน้า -> ทิ้ง
        "noise_patterns": [r"^CU iThesis .*$", r"^\d{10}(_\d{10})?$", r"^\d{1,3}$", r"^[ก-ฮ]$"],
        # เก็บเฉพาะบทที่มีเนื้อหาเชิงความรู้ (บท 3 = วิธีวิจัย, บท 4 = ตารางสถิติ -> ไม่ช่วยตอบคำถาม)
        "keep_chapters": {1: "background", 2: "theory", 5: "finding_discussion"},
        "extra_sections": [{"title": "บทคัดย่อ", "pages": [3, 3], "category": "abstract"}],
        "stop_headings": ["บรรณานุกรม", "ภาคผนวก"],
        "subheadings": [
            "งานวิจัยเกี่ยวกับความพึงพอใจในความสัมพันธ์", "สรุปผลการวิจัย", "อภิปรายผลการวิจัย",
            "ข้อได้เปรียบของการวิจัยในครั้งนี้", "ข้อจำกัดในการวิจัย",
            "ข้อเสนอแนะในการนำไปประยุกต์ใช้", "ข้อเสนอแนะสำหรับงานวิจัยในอนาคต",
        ],
    },
    {
        "source_id": "book_whonotlove",
        "file": DATA / "หนังสือใครไม่รักช่างแม่ง_ใช้ตอนอกหัก.pdf",
        "doc_type": "book",
        "title": "ใครไม่รักช่างแม่ง ใช้ตอนอกหัก",
        "year": None,
        "noise_patterns": [r"^\d{1,3}$"],
        "keep_chapters": None,          # ไม่มี "บทที่" -> ใช้ทั้งเล่มเป็น section เดียวต่อหน้า
        "default_category": "breakup_recovery",
        "extra_sections": [],
        "stop_headings": [],
        "subheadings": [],
    },
]
