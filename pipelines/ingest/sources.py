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
        # ใช้ทุกหน้า: ส่วนหน้า (ปก บทคัดย่อ กิตติกรรมประกาศ สารบัญ = หน้า 1-11) + บท 1-5 + บรรณานุกรม (ต่อท้ายบท 5)
        "keep_chapters": {1: "background", 2: "theory", 3: "method", 4: "results", 5: "finding_discussion"},
        "extra_sections": [{"title": "ส่วนหน้า: บทคัดย่อ กิตติกรรมประกาศ สารบัญ", "pages": [0, 10], "category": "abstract"}],
        "stop_headings": [],
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
    {
        "source_id": "article_multilove2565",
        "file": DATA / "คู่มือหาคู่.pdf",
        "doc_type": "research",
        "title": "ความรักหลากมิติ (ญาตาวีมินทร์ พืชทองหลาง, วารสารสหวิทยาการวิจัยและวิชาการ 2565)",
        "year": 2022,
        "source_quality": "academic",
        # header/citation ซ้ำทุกหน้า (18/18 หน้า)
        "noise_patterns": [r"^วารสารสหวิทยาการวิจัยและวิชาการ.*$", r"^Interdisciplinary Academic and Research Journal.*$",
                           r"^Website: https?://.*$", r"^DOI:.*$", r"^Citation:.*$", r"^Peuchthonglang, Y\..*$",
                           r"^ญาตาวีมินทร.*ความรักหลากมิติ.*$", r"^…+$", r"^\d{1,3}$", r"^\[\d{3}\]$"],
        "keep_chapters": None,
        "default_category": "theory",
        "extra_sections": [],
        "stop_headings": [],            # ใช้ทุกหน้า รวมเอกสารอ้างอิง (หน้า 17-18)
        "subheadings": [],
    },
    {
        "source_id": "web_pdf_shy_social",
        "file": DATA / "8 วิธีสร้างความมั่นใจให้คนขี้อายกล้าเข้าสังคม.pdf",
        "doc_type": "web_article",
        "title": "8 วิธีสร้างความมั่นใจให้คนขี้อายกล้าเข้าสังคม (bypichawee.co)",
        "year": None,
        "source_quality": "media",
        "url": None,
        "noise_patterns": [r"^8 วิธีสร้างความมั่นใจให้คนขี้อายกล้าเข้าสังคม$", r"^ณิชารีย์ ปานช่วยยาว.*$", r".*https?://.*", r"^\d{1,2}/\d{1,2}/\d{2} \d{1,2}:\d{2}$",
                           r"^\d+/\d+$"],
        "keep_chapters": None,
        "default_category": "interpersonal_skills",
        "extra_sections": [],
        "stop_headings": [],
        "subheadings": [],
    },
    {
        "source_id": "lecture_std_kku",
        "file": DATA / "โรคติดต่อทางเพศ.pdf",
        "doc_type": "lecture",
        "title": "โรคติดต่อทางเพศสัมพันธ์ (ผศ.ดร.เด่นพงศ์ พัฒนเศรษฐานนท์ คณะเภสัชศาสตร์ ม.ขอนแก่น)",
        "year": None,
        "source_quality": "academic",
        # ใช้ทุกหน้า (1-24) รวมชื่อยา/ขนาดยาสำหรับเภสัชกร -> คำตอบเรื่องสุขภาพต้องแนะนำให้พบแพทย์/เภสัชกร
        "noise_patterns": [r"^\d{1,3}$", r"^.*@gmail\.com$"],
        "keep_chapters": None,
        "default_category": "sexual_health",
        "tag_concepts": False,          # เนื้อหาการแพทย์: ไม่ผูก concept ความสัมพันธ์ (หลีกเลี่ยงยา -> avoidant, สัมผัสผิวหนัง -> touch)
        "extra_sections": [],
        "stop_headings": [],
        "subheadings": [],
    },
    *WEB_ARTICLES,
]

