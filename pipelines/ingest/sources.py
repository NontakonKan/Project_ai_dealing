"""ทะเบียนเอกสารต้นทาง + กติกาเฉพาะของแต่ละไฟล์ (config-driven ไม่ hardcode ใน logic)"""
from ..common.paths import DATA

# บทความเว็บ: เติมหัวข้อที่ PDF ยังไม่ครอบคลุม (red flag 4 ตัว + attach:fearful)
# source_quality: academic = บทความวิชาการจากคณะจิตวิทยา / media = สื่อสุขภาพ-ไลฟ์สไตล์ (ใช้เมื่อไม่มีแหล่งวิชาการ)
_WEB = [
    ("web_chula_gaslighting", "https://www.psy.chula.ac.th/en/feature-articles/gaslighting/",
     "Gaslighting…ผิดจริงหรือแค่ทริคทางจิตใจ? (คณะจิตวิทยา จุฬาฯ)", "toxic_relationship", "academic", 2022),
    ("web_chula_attachment", "https://www.psy.chula.ac.th/en/feature-articles/attachment-style",
     "Attachment style – รูปแบบความผูกพัน (คณะจิตวิทยา จุฬาฯ)", "theory", "academic", None),
    ("web_chula_anger", "https://www.psy.chula.ac.th/en/feature-articles/anger-management",
     "การจัดการอารมณ์โกรธ (คณะจิตวิทยา จุฬาฯ)", "emotion_regulation", "academic", None),
    ("web_chula_guilt_trip", "https://www.psy.chula.ac.th/en/feature-articles/guilt-trip/",
     "Guilt Trip ทริคทางจิตวิทยาของการควบคุมความสัมพันธ์ (คณะจิตวิทยา จุฬาฯ)", "toxic_relationship", "academic", None),
    ("web_chula_ipv", "https://www.psy.chula.ac.th/en/feature-articles/intimate-partner-violence/",
     "ความรุนแรงในคู่รัก (คณะจิตวิทยา จุฬาฯ)", "toxic_relationship", "academic", None),
    ("web_potential_boundary", "https://thepotential.org/life/healthy-boundary/",
     "ทำไมการมีจุดยืนที่ชัดเจนจึงสำคัญต่อการมีความสัมพันธ์ที่ดี (Healthy Boundary) — The Potential", "healthy_relationship", "media", None),
    ("web_healthaddict_friend_vs_partner",
     "https://www.healthaddict.com/content/Men'sAdvice:Choosingbetweenbestfriendandgirlfriend/",
     "รับมือยังไง? เมื่อต้องเลือกระหว่าง 'เพื่อน' กับ 'แฟน' — HealthAddict", "healthy_relationship", "media", None),
]
WEB_ARTICLES = [
    {"source_id": sid, "url": url, "doc_type": "web_article", "title": title, "year": year,
     "source_quality": quality, "noise_patterns": [r".*https?://.*"], "keep_chapters": None,
     "default_category": category, "extra_sections": [], "stop_headings": [], "subheadings": []}
    for sid, url, title, category, quality, year in _WEB
]


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
        "noise_patterns": [r"^\d{1,3}$", r"^```.*$", r"^ใครไม่รัก\s*\|\s*ช่าง.*$", r"^ข้อความในภาพคือ.*$"],
        "keep_chapters": None,          # ไม่มี "บทที่" -> 1 หน้า = 1 section แล้วรวมหน้าที่สั้นเกิน
        "default_category": "breakup_recovery",
        "extra_sections": [],
        "stop_headings": [],
        "subheadings": [],
    },
    {
        "source_id": "slides_winpeople",
        "file": DATA / "เทคนิคการครองใจคน.pdf",
        "doc_type": "slides",
        "title": "บทที่ 4 เทคนิคการครองใจคน (พฤติกรรมมนุษย์, Transactional Analysis, วิธีการสร้างมิตร)",
        "year": None,
        "noise_patterns": [r"^\d{1,3}$", r"^Ratthakorn Pongprasert$"],
        "keep_chapters": None,          # สไลด์: 1 หน้า = 1 section แล้วรวมสไลด์ที่สั้นเกิน
        "default_category": "interpersonal_skills",
        "extra_sections": [],
        "stop_headings": [],
        "subheadings": [],
    },
    *WEB_ARTICLES,
]

