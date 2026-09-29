# Data Card — คลังความรู้ PSU Dealing

> สร้างอัตโนมัติด้วย `python -m pipelines.ingest.data_card` จาก `data/processed/` — อย่าแก้ตัวเลขด้วยมือ

## 1. ภาพรวม

| | |
|---|---|
| แหล่งเอกสาร | **37** แหล่ง |
| chunk | **1,035** |
| chunk ที่มี concept (เชื่อม Graph) | 40.2% |
| ระดับความน่าเชื่อถือ | academic 956, document 27, media 26, education 9, media_public 7, research_institute 6, clinical 3, government 1 (นับเป็น chunk) |
| ชนิดเอกสาร | research 782, web_article 155, lecture 71, slides 27 |

**หมวด (category) ต่อ chunk:** relationship_initiation 242, theory 203, finding_discussion 143, interpersonal_skills 104, method 72, results 67, sexual_health 62, toxic_relationship 38, healthy_relationship 34, diversity 22, emotion_regulation 18, abstract 15, dating_safety 15

**เกณฑ์เลือกแหล่ง:** หน่วยงานรัฐ / มหาวิทยาลัย / วารสารวิชาการ (ThaiJO) / สถาบันวิจัย / โรงพยาบาล / สื่อสาธารณะ —
ไม่ใช้บล็อกไลฟ์สไตล์ · ข้อความต้องดึงจากต้นฉบับตรงๆ (ไม่สรุป ไม่แต่ง) · ทุกแหล่งมีชื่อที่อ้างอิงได้

## 2. รายการแหล่ง

| source_id | ชื่อ (ใช้อ้างอิงในคำตอบ) | ชนิด | ความน่าเชื่อถือ | หมวดตั้งต้น | หน้าที่ใช้ | chunk | มี concept | ที่มาข้อความ |
|---|---|---|---|---|---|---|---|---|
| `slides_winpeople` | บทที่ 4 เทคนิคการครองใจคน (พฤติกรรมมนุษย์, Transactional Analysis, วิธีการสร้างมิตร) | slides | document | interpersonal_skills | 39/40 | 27 | 44.4% | (text) |
| `article_multilove2565` | ความรักหลากมิติ (ญาตาวีมินทร์ พืชทองหลาง, วารสารสหวิทยาการวิจัยและวิชาการ 2565) | research | academic | theory | 18/18 | 40 | 60.0% | (text) |
| `web_pdf_shy_social` | 8 วิธีสร้างความมั่นใจให้คนขี้อายกล้าเข้าสังคม (บทความเว็บไซต์ By Pichawee) | web_article | media | interpersonal_skills | 2/3 | 5 | 20.0% | (text) |
| `lecture_std_kku` | โรคติดต่อทางเพศสัมพันธ์ (ผศ.ดร.เด่นพงศ์ พัฒนเศรษฐานนท์ คณะเภสัชศาสตร์ ม.ขอนแก่น) | lecture | academic | sexual_health | 24/24 | 62 | 0.0% | (text) |
| `thesis_start_romance2549` | การสื่อสารเพื่อการเริ่มต้นความสัมพันธ์ฉันคู่รักของวัยรุ่นไทย (วิทยานิพนธ์ คณะนิเทศศาสตร์ จุฬาฯ 2549) | research | academic | relationship_initiation | 161/161 | 225 | 23.6% | (ocr:vlm (cache)) |
| `thesis_attraction2548` | ความดึงดูดใจระหว่างบุคคลและรูปแบบความผูกพัน (วิทยานิพนธ์ คณะจิตวิทยา จุฬาฯ 2548) | research | academic | ตามบท | 178/178 | 225 | 66.7% | (text) |
| `thesis_narcissism2553` | อิทธิพลของความหลงตนเอง รูปแบบความรักแบบเล่นเกม และการกระตุ้นลักษณะเน้นความสัมพันธ์ต่อการผูกมัดในความสัมพันธ์ (วิทยานิพนธ์ คณะจิตวิทยา จุฬาฯ 2553) | research | academic | ตามบท | 165/165 | 229 | 31.9% | (text) |
| `web_chula_gaslighting` | Gaslighting…ผิดจริงหรือแค่ทริคทางจิตใจ? (คณะจิตวิทยา จุฬาฯ) | web_article | academic | toxic_relationship | 1/1 | 4 | 75.0% | (web) |
| `web_chula_attachment` | Attachment style – รูปแบบความผูกพัน (คณะจิตวิทยา จุฬาฯ) | web_article | academic | theory | 1/1 | 6 | 100.0% | (web) |
| `web_chula_anger` | การจัดการอารมณ์โกรธ (คณะจิตวิทยา จุฬาฯ) | web_article | academic | emotion_regulation | 1/1 | 11 | 90.9% | (web) |
| `web_chula_guilt_trip` | Guilt Trip ทริคทางจิตวิทยาของการควบคุมความสัมพันธ์ (คณะจิตวิทยา จุฬาฯ) | web_article | academic | toxic_relationship | 1/1 | 7 | 85.7% | (web) |
| `web_chula_ipv` | ความรุนแรงในคู่รัก (คณะจิตวิทยา จุฬาฯ) | web_article | academic | toxic_relationship | 1/1 | 9 | 88.9% | (web) |
| `web_potential_boundary` | ทำไมการมีจุดยืนที่ชัดเจนจึงสำคัญต่อการมีความสัมพันธ์ที่ดี (Healthy Boundary) — The Potential | web_article | media | healthy_relationship | 1/1 | 6 | 100.0% | (web) |
| `web_healthaddict_friend_vs_partner` | รับมือยังไง? เมื่อต้องเลือกระหว่าง 'เพื่อน' กับ 'แฟน' — HealthAddict | web_article | media | healthy_relationship | 1/1 | 2 | 50.0% | (web) |
| `chula_dating_hookup` | การออกเดท และวัฒนธรรมการ Hook up (คณะจิตวิทยา จุฬาฯ) | web_article | academic | relationship_initiation | 3/3 | 7 | 57.1% | (text) |
| `chula_situationships` | Situationships: สถานะ....ไม่มีสถานะ (คณะจิตวิทยา จุฬาฯ) | web_article | academic | relationship_initiation | 2/2 | 4 | 100.0% | (text) |
| `chula_unrequited_love` | การตบมือข้างเดียวของความรัก (คณะจิตวิทยา จุฬาฯ) | web_article | academic | relationship_initiation | 3/3 | 6 | 33.3% | (text) |
| `chula_true_love_check` | ดูผู้ชายอย่างไร ว่าใครรักจริงหวังแต่ง (คณะจิตวิทยา จุฬาฯ) | web_article | academic | healthy_relationship | 3/3 | 7 | 28.6% | (text) |
| `chula_long_distance` | รักษารักทางไกลให้หวานชื่น (คณะจิตวิทยา จุฬาฯ) | web_article | academic | healthy_relationship | 3/3 | 5 | 40.0% | (text) |
| `chula_love_fresh_up` | เติมความสดใสให้กับความรัก (คณะจิตวิทยา จุฬาฯ) | web_article | academic | healthy_relationship | 3/3 | 8 | 62.5% | (text) |
| `chula_teen_romance_parents` | เมื่อลูกวัยรุ่นมีแฟน ชวนพ่อแม่มองข้อดีต่อพัฒนาการ (คณะจิตวิทยา จุฬาฯ) | web_article | academic | healthy_relationship | 3/3 | 6 | 66.7% | (text) |
| `chula_adults_minors` | ทำไมความสัมพันธ์เชิงชู้สาวระหว่างผู้ใหญ่และเด็กอายุต่ำกว่า 18 ปีจึงน่ากังวล (คณะจิตวิทยา จุฬาฯ) | web_article | academic | toxic_relationship | 3/3 | 6 | 50.0% | (text) |
| `chula_gender_identity` | ความหลากหลายทางเพศในสังคมไทย (คณะจิตวิทยา จุฬาฯ) | web_article | academic | diversity | 4/4 | 6 | 66.7% | (text) |
| `chula_lesbian` | เข้าใจจิตใจ หญิงรักหญิง (คณะจิตวิทยา จุฬาฯ) | web_article | academic | diversity | 4/4 | 7 | 14.3% | (text) |
| `chula_coming_out` | การเปิดเผยความโน้มเอียงทางเพศแบบรักเพศเดียวกัน (คณะจิตวิทยา จุฬาฯ) | web_article | academic | diversity | 5/5 | 9 | 44.4% | (text) |
| `chula_counseling_benefits` | เมื่อไรที่จะมาหานักจิตวิทยาการปรึกษา (คณะจิตวิทยา จุฬาฯ) | web_article | academic | emotion_regulation | 2/2 | 4 | 0.0% | (text) |
| `manarom_jealousy` | หวงรัก อารมณ์หึงหวง (นักจิตวิทยา โรงพยาบาลมนารมย์) | web_article | clinical | emotion_regulation | 2/2 | 3 | 100.0% | (text) |
| `thaipbs_ghosting` | จิตวิทยาน่ารู้: หายไปไม่บอกกล่าว เจ็บปวดนานกว่าถูกปฏิเสธโดยตรง (Thai PBS) | web_article | media_public | toxic_relationship | 3/3 | 5 | 80.0% | (text) |
| `thaipbs_dating_app_scam` | ปัดแอปหาคู่ แต่เจอมิจฉาชีพ (Thai PBS อ้างอิง บช.สอท.) | web_article | media_public | dating_safety | 1/1 | 1 | 0.0% | (text) |
| `thaipbs_dating_app_safe` | เล่นแอปหาคู่อย่างไร ไม่ถูกหลอก (Thai PBS อ้างอิง ตำรวจสอบสวนกลาง) | web_article | media_public | dating_safety | 1/1 | 1 | 100.0% | (text) |
| `secnia_dating_app` | บทเรียนแอปพลิเคชันหาคู่ หลอกให้รัก-ลวงล่วงละเมิด-หลอกลงทุน (ผู้จัดการออนไลน์ 2565) | web_article | media | dating_safety | 3/3 | 6 | 66.7% | (text) |
| `tdri_romance_scam` | กลลวงจากความเหงา Romance scam รักหลอก โอน (สถาบันวิจัยเพื่อการพัฒนาประเทศไทย TDRI) | web_article | research_institute | dating_safety | 3/3 | 6 | 100.0% | (text) |
| `police9_romance_scam` | หลอกให้รักแล้วชวนลงทุน Romance Scam (ตำรวจภูธรภาค 9) | web_article | government | dating_safety | 1/1 | 1 | 0.0% | (text) |
| `potential_love_bombing` | Love Bombing: เมื่อการทุ่มเทความรักมากมายเป็นเพียงเหยื่อล่อไปสู่ความสัมพันธ์ท็อกซิก (The Potential) | web_article | media | toxic_relationship | 4/4 | 7 | 100.0% | (text) |
| `dltv_refusal` | ใบความรู้ ทักษะการปฏิเสธ (มูลนิธิการศึกษาทางไกลผ่านดาวเทียม DLTV) | lecture | education | interpersonal_skills | 5/5 | 9 | 33.3% | (text) |
| `thaijo_address_terms` | คำเรียกขานในภาษาไทยตามปัจจัยอายุ เพศ และความสัมพันธ์ของผู้พูด (วริษา สารวิทย์ ม.นเรศวร, Rajabhat J. Sci. Humanit. Soc. Sci. 2559) | research | academic | interpersonal_skills | 11/11 | 28 | 0.0% | (text) |
| `thaijo_pronouns_students` | การใช้คำสรรพนามบุรุษที่ 1 และบุรุษที่ 2: กรณีศึกษานักศึกษามหาวิทยาลัยแม่ฟ้าหลวง (แอล เซอร์ดาร์ และ ธีระ บุษบกแก้ว, วารสารวิชาการมนุษยศาสตร์และสังคมศาสตร์ มรภ.ธนบุรี 2565) | research | academic | interpersonal_skills | 14/14 | 35 | 0.0% | (text) |

## 3. แหล่งที่ตัดออก

| id | หน่วยงาน | เหตุผล |
|---|---|---|
| `bbl_romance_scam` | ธนาคารกรุงเทพ | ธนาคารกรุงเทพบล็อกการดาวน์โหลดอัตโนมัติ |
| `dmh_refusal_teen` | กรมสุขภาพจิต กระทรวงสาธารณสุข | หน้าเว็บโหลดเนื้อหาด้วยสคริปต์ ดึงข้อความไม่ได้ |
| `bnh_love_bombing` | โรงพยาบาลบีเอ็นเอช (BNH Hospital) | เว็บบล็อกการดาวน์โหลดอัตโนมัติ (HTTP 403) — ไม่หลบการบล็อก |
| `ooca_love_bombing` | ooca (แพลตฟอร์มปรึกษานักจิตวิทยา/จิตแพทย์) | เว็บบล็อกการดาวน์โหลดอัตโนมัติ (HTTP 403) — ไม่หลบการบล็อก |
| `research_cu2561` |  | ผู้ดูแลถอดไฟล์ออกจากคลัง (คำถามทดสอบ Q02, Q05 เปลี่ยนเป็น 'ต้องปฏิเสธ') |
| `book_whonotlove` |  | ผู้ดูแลถอดไฟล์ออกจากคลัง |
| `thesis_online_romance2557` |  | ผู้ดูแลถอดไฟล์ออกจากคลัง |
| `royal_qa` |  | ผู้ดูแลถอดไฟล์ออกจากคลัง |

## 4. การเตรียมข้อมูล (ขั้นตอน)

1. **ดึงข้อความ:** PDF ที่มี text layer ใช้ PyMuPDF / PDF สแกนใช้ VLM OCR (qwen2.5vl) / หน้าเว็บดึงจาก HTML แล้วทำ PDF ที่มีหัวอ้างอิง (`pipelines/ingest/collect.py`)
2. **ทำความสะอาด:** แก้ฟอนต์ไทยเก่า (PUA) 20,165 จุด, สระอำแตก 387 จุด, ลบบรรทัดขยะ (เลขหน้า หัวกระดาษ ตราดาวน์โหลด) 4,018 บรรทัด, ตัดเลขอ้างอิงในเนื้อความ 37 จุด
3. **แบ่งส่วน:** ตามบทของวิทยานิพนธ์ / ตามหน้า / รวม section ที่สั้นกว่า 80 คำ
4. **ตัด chunk:** 300 คำ ซ้อนกัน 15% (นับคำด้วย PyThaiNLP)
5. **ตัด chunk ซ้ำ:** 18 chunk (ภาคผนวกที่พิมพ์แบบสอบถามชุดเดิมซ้ำหลายเงื่อนไข)
6. **ติด metadata + concept:** ใช้ `data/concept_lexicon.json` + กฎบริบท (±60 ตัวอักษร, คำปฏิเสธ, คำต่อท้าย)
7. **ปกปิดข้อมูลส่วนบุคคล:** ตัดอีเมลผู้เขียนงานวิจัยด้วย noise pattern — pipeline มีกลไกปกปิดชื่อบุคคล (`redact`, `name_capture`) ที่เคยใช้กับเอกสารถาม-ตอบของเยาวชน ซึ่งถูกถอดออกจากคลังแล้ว

## 5. ขนาด chunk และเหตุผล

| | p50 | p95 | max |
|---|---|---|---|
| คำ (PyThaiNLP) | 261 | 305 | 345 |
| token (bge-m3) | 323 | 441 | 962 |

- **300 คำ:** ใหญ่พอให้ 1 chunk มีทั้งประเด็นและคำอธิบาย (ย่อหน้าวิชาการไทยยาว) และเล็กพอให้ใส่ 3–4 chunk ใน context 3,000 token ของ LLM
- **embedding (bge-m3 รับได้ 8,192 token):** ทุก chunk อยู่ในขีดจำกัด
- **reranker (bge-reranker-v2-m3 อ่านได้ 512 token):** chunk ที่เกิน 512 token มี 17 อัน (1.6%) -> ด่านความเกี่ยวข้องอ่านเป็นช่วงละ 600 ตัวอักษร ซ้อน 150 (`gate._windows`) เพื่อไม่ให้ท้าย chunk ถูกตัดทิ้ง
- **overlap 15%:** ประโยคที่คร่อมรอยตัดยังอยู่ครบใน chunk ใดอันหนึ่ง + ขั้นค้นหาดึง chunk ข้างเคียงมาตรวจด้วย (`search._neighbors`)

## 6. Metadata ต่อ chunk

| field | ใช้ทำอะไร |
|---|---|
| chunk_id | `<source>_s<section>_c<chunk>` คงที่ข้ามการรัน (chunk ซ้ำที่ถูกตัดจะเว้นเลข) |
| source_id / title / year / url | ที่มาสำหรับอ้างอิงในคำตอบ (title ไม่ใส่โดเมน เพราะ LINE แปลงเป็นลิงก์) |
| doc_type / source_quality | ชนิดเอกสาร / ระดับความน่าเชื่อถือ (academic, clinical, government, …) |
| chapter / section_title / pages | ตำแหน่งในเอกสาร (หน้าเริ่มจาก 0) |
| category | หมวดสำหรับ router (เช่น sexual_health ถูกกันไม่ให้หลุดไปตอบเรื่องจับคู่) |
| concepts / concept_counts | taxonomy id ชุดเดียวกับโปรไฟล์ผู้ใช้และ Graph -> สร้าง edge ABOUT |
| topics / target_trait | หัวข้อย่อย / concept ที่เป็นลักษณะบุคคล (trait, attach) |
| n_words / n_chars / lang | ขนาด chunk (คำนับด้วย PyThaiNLP) |

## 7. การเตรียมข้อมูลสำหรับ Vector และ Graph

- **Vector (Dense):** ทุก chunk -> bge-m3 -> ChromaDB (`python -m pipelines.dense.run build`)
- **Graph:** chunk เป็น node `BookChunk`, concept -> edge `ABOUT` ไปยัง node Concept ชุดเดียวกับโปรไฟล์ผู้ใช้
  ทำให้ค้นจากลักษณะของคู่ (trait / red flag) ไปหาความรู้ได้ตรงๆ (`python -m graph.build`)

## 8. การควบคุมคุณภาพ

| ตรวจอะไร | ผล | ที่มา |
|---|---|---|
| OCR เทียบหน้าที่ถอดด้วยมือ | CER 8.0% -> 4.3%, WER 14.6% -> 11.2% | `pipelines/ingest/ocr_eval.py` |
| หน้าที่คนตรวจจากภาพ (แทน OCR) | 101 หน้า | `data/ocr_verified/` |
| PDF จากเว็บ อ่านกลับได้ตรงต้นฉบับ | 99.7–100% (หายเฉพาะอีโมจิ) | `pipelines/ingest/collect.py` |
| chunk ซ้ำ | ตัด 18 | `run.dedupe` |
| concept tag สุ่มตรวจ 50 คู่ | precision 76% -> 80.9% หลังแก้คำปฏิเสธ (วัดในชุดเดิม) | `pipelines/ingest/tag_audit.py` |

**ประเภทข้อผิดพลาดที่พบ (ก่อนแก้):** คำปฏิเสธ (3), อยู่ในบรรณานุกรม ไม่ใช่เนื้อหา (2), เปิดเผยตนเอง (self-disclosure) ไม่ใช่การพูดตรง (1), ครอบครัวอบอุ่น ไม่ใช่นิสัยใจดีของคน (1), ความใกล้ชิดของวัยรุ่นกับเพื่อน ไม่ใช่ความใกล้ชิดแบบคู่รัก (1), 'มีเหตุผลอะไรบ้าง' = เหตุผลที่ทำ ไม่ใช่นิสัยมีเหตุผล (1), 'ดูแลตัวเอง' = พึ่งพาตัวเองได้ ไม่ใช่การดูแลรูปลักษณ์ (1), คำคร่อมกัน (1), 'รับผิดชอบ' = หน้าที่การงาน ไม่ใช่นิสัย (1)
— แก้คำปฏิเสธแล้ว (ผิด 3 -> 0 ในชุดเดิม โดย tag ที่ถูกไม่หาย) ส่วนความหมายต่างบริบท / บรรณานุกรม ยังเป็นข้อจำกัด
(ผู้ตรวจ: Claude (อ่านบริบททีละคู่) — ควรให้คนยืนยันซ้ำ)

## 9. ข้อมูลผู้ใช้จำลอง (สำหรับจับคู่)

- `data/mock/users.json` ผู้ใช้สังเคราะห์ 300 คน + แชท / เหตุการณ์ / คู่เฉลย (`ground_truth_pairs.json`)
- เป็นข้อมูลสังเคราะห์ -> ใช้ทดสอบกลไก ไม่ได้วัดความแม่นในโลกจริง

## 10. ลิขสิทธิ์และข้อมูลส่วนบุคคล

- เอกสารส่วนใหญ่มีลิขสิทธิ์ -> ใช้เพื่อการศึกษา, repo ต้องเป็น **private**, คำตอบอ้างอิงชื่อแหล่งทุกครั้ง
- ไม่เก็บ/ไม่ส่งให้ LLM: ศาสนา อาหาร (ต้องยินยอม), LINE ID / เบอร์ / อีเมลในแชท (ตัดก่อนเก็บความจำ)
- แชทผู้ใช้จริง (`data/app/*.db`) และ API key (`.env`) ไม่ขึ้น git
