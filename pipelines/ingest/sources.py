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
        "title": "8 วิธีสร้างความมั่นใจให้คนขี้อายกล้าเข้าสังคม (บทความเว็บไซต์ By Pichawee)",   # ไม่ใส่โดเมน: LINE แปลงเป็นลิงก์
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
    {
        "source_id": "thesis_start_romance2549",
        # วิทยานิพนธ์สแกน (ไม่มี text layer) แยกเป็น 7 ไฟล์ตามบท -> OCR ทีละไฟล์ แล้วต่อเป็นเล่มเดียว
        "files": [DATA / f"การสื่อสารเพื่อการเริ่มต้นความสัมพันธ์ฉันคู่รักของวัยรุ่นไทย{i}.pdf" for i in range(1, 8)],
        "doc_type": "research",
        "title": "การสื่อสารเพื่อการเริ่มต้นความสัมพันธ์ฉันคู่รักของวัยรุ่นไทย (วิทยานิพนธ์ คณะนิเทศศาสตร์ จุฬาฯ 2549)",
        "year": 2006,
        "source_quality": "academic",
        # + ตราดาวน์โหลดของคลังจุฬาฯ ทุกหน้า ("โดย ผู้ใช้ทั่วไป", "ดาวน์โหลดเมื่อ 28/09/2569 ...") ที่ OCR อ่านเพี้ยนต่างกันไป
        "noise_patterns": [r"^\d{1,3}$", r"^[ก-ฮ]$", r"^\S{0,4}\s*ผู้\S{0,6}ทั่วไป$", r"^\S*โหลดเมื่อ.*$"],
        "keep_chapters": None,          # OCR: หัวบทไม่แน่นอน -> 1 หน้า = 1 section แล้วรวมหน้าที่สั้นเกิน
        "default_category": "relationship_initiation",
        "extra_sections": [],
        "stop_headings": [],
        "subheadings": [],
    },
    {
        "source_id": "thesis_attraction2548",
        "file": DATA / "ความดึงดูดระหว่างบุคคล.pdf",
        "doc_type": "research",
        "title": "ความดึงดูดใจระหว่างบุคคลและรูปแบบความผูกพัน (วิทยานิพนธ์ คณะจิตวิทยา จุฬาฯ 2548)",
        "year": 2005,
        "source_quality": "academic",
        "noise_patterns": [r"^\d{1,3}$", r"^[ก-ฮ]$"],
        # ใช้ทุกหน้า: ส่วนหน้า (หน้า 1-12) + บท 1-5 + รายการอ้างอิง/ภาคผนวก (ต่อท้ายบท 5)
        # แบบคณะจิตวิทยา: บท 1 = บทนำ+ทฤษฎี, 2 = วิธีวิจัย, 3 = ผล, 4 = อภิปราย, 5 = สรุป
        "keep_chapters": {1: "theory", 2: "method", 3: "results", 4: "finding_discussion", 5: "finding_discussion"},
        "extra_sections": [{"title": "ส่วนหน้า: บทคัดย่อ กิตติกรรมประกาศ สารบัญ", "pages": [0, 11], "category": "abstract"}],
        "stop_headings": [],
        "subheadings": [],
    },
    {
        "source_id": "thesis_narcissism2553",
        "file": DATA / "หลงตัวเอง.pdf",
        "doc_type": "research",
        "title": "อิทธิพลของความหลงตนเอง รูปแบบความรักแบบเล่นเกม และการกระตุ้นลักษณะเน้นความสัมพันธ์ต่อการผูกมัดในความสัมพันธ์ (วิทยานิพนธ์ คณะจิตวิทยา จุฬาฯ 2553)",
        "year": 2010,
        "source_quality": "academic",
        "noise_patterns": [r"^\d{1,3}$", r"^[ก-ฮ]$"],
        "keep_chapters": {1: "theory", 2: "method", 3: "results", 4: "finding_discussion", 5: "finding_discussion"},
        "extra_sections": [{"title": "ส่วนหน้า: บทคัดย่อ กิตติกรรมประกาศ สารบัญ", "pages": [0, 10], "category": "abstract"}],
        "stop_headings": [],
        "subheadings": [],
    },
    *WEB_ARTICLES,
]

