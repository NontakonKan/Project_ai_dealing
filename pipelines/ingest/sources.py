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

# เอกสารเพิ่ม 2569: เติมหมวดที่บอทตอบไม่ได้ (ความปลอดภัยแอปหาคู่ / red flag ช่วงแรก / การปฏิเสธ / คำเรียกขาน / เดต / ghosting
# / หึงหวง / LGBTQ+) — เก็บด้วย pipelines/ingest/collect.py (รายการแหล่ง+URL: data/new_docs/candidates.json)
# PDF จากหน้าเว็บมีหัวอ้างอิง (ที่มา/URL/วันที่เข้าถึง) ในหน้าแรก -> ตัดทิ้งด้วย _HEADER
_HEADER = [r"^ที่มา: .*$", r"^เข้าถึงเมื่อ .*$", r".*https?://.*", r".*www\.\S+.*"]
_CHULA = "คณะจิตวิทยา จุฬาฯ"
_DOCS = [
    # (source_id, ไฟล์, ชื่อที่ใช้อ้างอิง (ไม่ใส่โดเมน: LINE แปลงเป็นลิงก์), หมวด, ความน่าเชื่อถือ, ปี, doc_type, noise เพิ่ม)
    ("chula_dating_hookup", "การออกเดทและวัฒนธรรมการ Hook up.pdf", f"การออกเดท และวัฒนธรรมการ Hook up ({_CHULA})",
     "relationship_initiation", "academic", 2024, "web_article", []),
    ("chula_situationships", "Situationships สถานะไม่มีสถานะ.pdf", f"Situationships: สถานะ....ไม่มีสถานะ ({_CHULA})",
     "relationship_initiation", "academic", 2026, "web_article", []),
    ("chula_unrequited_love", "การตบมือข้างเดียวของความรัก.pdf", f"การตบมือข้างเดียวของความรัก ({_CHULA})",
     "relationship_initiation", "academic", 2023, "web_article", []),
    ("chula_true_love_check", "ดูผู้ชายอย่างไรว่าใครรักจริงหวังแต่ง.pdf", f"ดูผู้ชายอย่างไร ว่าใครรักจริงหวังแต่ง ({_CHULA})",
     "healthy_relationship", "academic", None, "web_article", []),
    ("chula_long_distance", "รักษารักทางไกลให้หวานชื่น.pdf", f"รักษารักทางไกลให้หวานชื่น ({_CHULA})",
     "healthy_relationship", "academic", 2017, "web_article", []),
    ("chula_love_fresh_up", "เติมความสดใสให้กับความรัก.pdf", f"เติมความสดใสให้กับความรัก ({_CHULA})",
     "healthy_relationship", "academic", None, "web_article", []),
    ("chula_teen_romance_parents", "เมื่อลูกวัยรุ่นมีแฟน.pdf", f"เมื่อลูกวัยรุ่นมีแฟน ชวนพ่อแม่มองข้อดีต่อพัฒนาการ ({_CHULA})",
     "healthy_relationship", "academic", 2024, "web_article", []),
    ("chula_adults_minors", "ความสัมพันธ์เชิงชู้สาวระหว่างผู้ใหญ่และเด็ก.pdf",
     f"ทำไมความสัมพันธ์เชิงชู้สาวระหว่างผู้ใหญ่และเด็กอายุต่ำกว่า 18 ปีจึงน่ากังวล ({_CHULA})",
     "toxic_relationship", "academic", 2025, "web_article", []),
    ("chula_gender_identity", "ความหลากหลายทางเพศในสังคมไทย.pdf", f"ความหลากหลายทางเพศในสังคมไทย ({_CHULA})",
     "diversity", "academic", 2019, "web_article", []),
    ("chula_lesbian", "เข้าใจจิตใจหญิงรักหญิง.pdf", f"เข้าใจจิตใจ หญิงรักหญิง ({_CHULA})",
     "diversity", "academic", None, "web_article", []),
    ("chula_coming_out", "การเปิดเผยความโน้มเอียงทางเพศ (Coming out).pdf", f"การเปิดเผยความโน้มเอียงทางเพศแบบรักเพศเดียวกัน ({_CHULA})",
     "diversity", "academic", 2022, "web_article", []),
    ("chula_counseling_benefits", "เมื่อไรที่จะมาหานักจิตวิทยาการปรึกษา.pdf", f"เมื่อไรที่จะมาหานักจิตวิทยาการปรึกษา ({_CHULA})",
     "emotion_regulation", "academic", 2019, "web_article", []),
    ("manarom_jealousy", "อารมณ์หึงหวง.pdf", "หวงรัก อารมณ์หึงหวง (นักจิตวิทยา โรงพยาบาลมนารมย์)",
     "emotion_regulation", "clinical", None, "web_article", []),
    ("thaipbs_ghosting", "หายไปไม่บอกกล่าว (Ghosting).pdf", "จิตวิทยาน่ารู้: หายไปไม่บอกกล่าว เจ็บปวดนานกว่าถูกปฏิเสธโดยตรง (Thai PBS)",
     "toxic_relationship", "media_public", None, "web_article", []),
    ("thaipbs_dating_app_scam", "แอปหาคู่แต่เจอมิจฉาชีพ.pdf", "ปัดแอปหาคู่ แต่เจอมิจฉาชีพ (Thai PBS อ้างอิง บช.สอท.)",
     "dating_safety", "media_public", None, "web_article", []),
    ("thaipbs_dating_app_safe", "เล่นแอปหาคู่อย่างไรไม่ถูกหลอก.pdf", "เล่นแอปหาคู่อย่างไร ไม่ถูกหลอก (Thai PBS อ้างอิง ตำรวจสอบสวนกลาง)",
     "dating_safety", "media_public", None, "web_article", []),
    ("secnia_dating_app", "บทเรียนแอปพลิเคชันหาคู่.pdf", "บทเรียนแอปพลิเคชันหาคู่ หลอกให้รัก-ลวงล่วงละเมิด-หลอกลงทุน (ผู้จัดการออนไลน์ 2565)",
     "dating_safety", "media", 2022, "web_article", []),
    ("tdri_romance_scam", "กลลวงจากความเหงา Romance scam.pdf", "กลลวงจากความเหงา Romance scam รักหลอก โอน (สถาบันวิจัยเพื่อการพัฒนาประเทศไทย TDRI)",
     "dating_safety", "research_institute", 2026, "web_article", []),
    ("police9_romance_scam", "หลอกให้รักแล้วชวนลงทุน.pdf", "หลอกให้รักแล้วชวนลงทุน Romance Scam (ตำรวจภูธรภาค 9)",
     "dating_safety", "government", None, "web_article", [r"^#.*$"]),
    ("potential_love_bombing", "Love Bombing เหยื่อล่อสู่ความสัมพันธ์ท็อกซิก.pdf",
     "Love Bombing: เมื่อการทุ่มเทความรักมากมายเป็นเพียงเหยื่อล่อไปสู่ความสัมพันธ์ท็อกซิก (The Potential)",
     "toxic_relationship", "media", None, "web_article", []),
    ("dltv_refusal", "ทักษะการปฏิเสธ.pdf", "ใบความรู้ ทักษะการปฏิเสธ (มูลนิธิการศึกษาทางไกลผ่านดาวเทียม DLTV)",
     "interpersonal_skills", "education", None, "lecture", [r"^\d{1,3}$"]),
    ("thaijo_address_terms", "คำเรียกขานในภาษาไทยตามอายุ เพศ และความสัมพันธ์.pdf",
     "คำเรียกขานในภาษาไทยตามปัจจัยอายุ เพศ และความสัมพันธ์ของผู้พูด (วริษา สารวิทย์ ม.นเรศวร, Rajabhat J. Sci. Humanit. Soc. Sci. 2559)",
     "interpersonal_skills", "academic", 2016, "research", [r"^Rajabhat J\. Sci\..*$", r".*e-mail.*", r"^\d{1,3}$"]),
    ("thaijo_pronouns_students", "การใช้คำสรรพนามของนักศึกษา.pdf",
     "การใช้คำสรรพนามบุรุษที่ 1 และบุรุษที่ 2: กรณีศึกษานักศึกษามหาวิทยาลัยแม่ฟ้าหลวง (แอล เซอร์ดาร์ และ ธีระ บุษบกแก้ว, วารสารวิชาการมนุษยศาสตร์และสังคมศาสตร์ มรภ.ธนบุรี 2565)",
     "interpersonal_skills", "academic", 2022, "research", [r".*e-mail.*", r"^\d{1,3}$", r"^-$"]),
]
NEW_DOCS = [
    {"source_id": sid, "file": DATA / fname, "doc_type": doc_type, "title": title, "year": year,
     "source_quality": quality, "url": None, "noise_patterns": _HEADER + noise, "keep_chapters": None,
     "default_category": category, "extra_sections": [], "stop_headings": [], "subheadings": []}
    for sid, fname, title, category, quality, year, doc_type, noise in _DOCS
]
# งานวิจัยภาษาศาสตร์: "สนิท/ไม่สนิท" = ความคุ้นเคยตอนเรียกขาน ไม่ใช่ความใกล้ชิดแบบคู่รัก (วัดจริง: ติด love:intimacy ผิด 19 chunk)
for _d in NEW_DOCS:
    if _d["source_id"].startswith("thaijo_"):
        _d["tag_concepts"] = False


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
    *NEW_DOCS,
]

