"""การทดสอบการสกัดข้อมูลหลายมิติใน 1 ประโยค (Persona vs Wants), คณะ 5 วิทยาเขต, การพิมพ์ผิด, และ Guards"""
import unittest

from app.replies import SYSTEM, format_learned
from pipelines.llm import guards, schemas
from pipelines.profile import faculty


class MultiExtractionAndGuardsTests(unittest.TestCase):
    def test_multi_campus_faculties_and_typos(self):
        # หาดใหญ่ + คำพิมพ์ผิด
        self.assertEqual(faculty.normalize("วิดวะ"), "วิศวกรรมศาสตร์")
        self.assertEqual(faculty.normalize("แพท"), "แพทยศาสตร์")
        self.assertEqual(faculty.normalize("เพสัช"), "เภสัชศาสตร์")
        self.assertEqual(faculty.normalize("พยาบาน"), "พยาบาลศาสตร์")
        self.assertEqual(faculty.normalize("ถาปัด"), "สถาปัตยกรรมศาสตร์")
        self.assertEqual(faculty.normalize("นิดติ"), "นิติศาสตร์")
        self.assertEqual(faculty.normalize("รัดสาด"), "รัฐศาสตร์")
        self.assertEqual(faculty.normalize("สินสาด"), "ศิลปศาสตร์")

        # ปัตตานี
        self.assertEqual(faculty.normalize("ศึกษาศาสตร์"), "ศึกษาศาสตร์")
        self.assertEqual(faculty.normalize("มนุษยศาสตร์"), "มนุษยศาสตร์และสังคมศาสตร์")
        self.assertEqual(faculty.normalize("นิเทศ"), "วิทยาการสื่อสาร")
        self.assertEqual(faculty.normalize("อิสลามศึกษา"), "วิทยาลัยอิสลามศึกษา")

        # ภูเก็ต
        self.assertEqual(faculty.normalize("การท่องเที่ยว"), "การบริการและการท่องเที่ยว")
        self.assertEqual(faculty.normalize("วิทยาลัยการคอมพิวเตอร์"), "วิทยาลัยการคอมพิวเตอร์")
        self.assertEqual(faculty.normalize("วิเทศ"), "วิเทศศึกษา")

        # สุราษฎร์ธานี & ตรัง
        self.assertEqual(faculty.normalize("วิทย์อุต"), "วิทยาศาสตร์และเทคโนโลยีอุตสาหกรรม")
        self.assertEqual(faculty.normalize("บัญชีตรัง"), "พาณิชยศาสตร์และการจัดการ")

    def test_multi_entity_sentence_parsing(self):
        # 1 ประโยคมีทั้งสเปกคนอ่านหนังสือ คณะแพทย์ และงานอดิเรกตัวเอง
        res = faculty.parse("ชอบคนอ่านหนังสือเยอะ เรียนคณะแพทย์ เวลาว่างชอบดูหนัง")
        self.assertIsNone(res["self"])
        self.assertIn("แพทยศาสตร์", res["wants"])
        self.assertTrue(any("แพทย์" in s for s in res["spans"]))

        # ประโยคบอกทั้งของตัวเองและของคู่
        res2 = faculty.parse("ผมเรียนวิศวะ อยากได้แฟนเรียนนิติ")
        self.assertEqual(res2["self"], "วิศวกรรมศาสตร์")
        self.assertIn("นิติศาสตร์", res2["wants"])

    def test_drop_invalid_avoids(self):
        # "คนนิสัยนิ่งๆ" ถูกสับสนเป็น avoids -> ต้องย้ายไป wants: trait:calm
        clean = {
            "wants": [],
            "avoids": [{"id": "rf:possessive", "evidence": "นิ่งๆ"}],
        }
        guards.drop_invalid_avoids(clean, "ชอบคนนิสัยนิ่งๆ")
        self.assertEqual(clean["avoids"], [])
        self.assertEqual(clean["wants"][0]["id"], "trait:calm")

        # ข้อความบอกชอบ แต่ถูกดึงเข้า avoids -> ต้องถูกตัดทิ้ง
        clean2 = {
            "wants": [],
            "avoids": [{"id": "trait:kind", "evidence": "ใจดี"}],
        }
        guards.drop_invalid_avoids(clean2, "ชอบคนใจดี")
        self.assertEqual(clean2["avoids"], [])

    def test_drop_faculty_hallucination(self):
        # evidence เป็นเรื่องคณะใน wants -> ต้องถูกตัดทิ้งเพื่อไม่ให้ชนกับระบบ faculty
        clean = {
            "wants": [{"id": "hygiene:self_care", "evidence": "เรียนคณะแพทย์"}],
            "hobbies": [{"id": "hobby:movies", "evidence": "ดูหนัง"}],
        }
        guards.drop_faculty_hallucinations(clean, "ชอบคนอ่านหนังสือเยอะ เรียนคณะแพทย์ เวลาว่างชอบดูหนัง")
        self.assertEqual(clean["wants"], [])
        self.assertEqual(len(clean["hobbies"]), 1)

    def test_schemas_wants_allows_hobbies(self):
        self.assertIn("hobbies", schemas.PROFILE_FIELDS["wants"])

    def test_format_learned(self):
        learned_ids = ["hobby:movies", "wants:hobby:reading", "อยากได้คนเรียนคณะแพทยศาสตร์"]
        formatted = format_learned(learned_ids)
        self.assertIn("ความชอบส่วนตัวของผู้ใช้", formatted)
        self.assertIn("ดูหนัง", formatted)
        self.assertIn("สเปกคู่ที่ชอบ", formatted)
        self.assertIn("อ่านหนังสือ", formatted)
        self.assertIn("อยากได้คนเรียนคณะแพทยศาสตร์", formatted)

    def test_system_prompt_out_of_domain_guardrail(self):
        self.assertIn("Out-of-Domain Guardrail", SYSTEM)
        self.assertIn("แมวกับไก่ ตัวอะไรอร่อยกว่า", SYSTEM)
        self.assertIn("ห้ามเล่นตามน้ำ", SYSTEM)

    def test_out_of_domain_intent_classification(self):
        from app import intent_model
        for q in ["หมากับแมวอะไรน่ารักกว่า", "แมวกับไก่ ตัวอะไรอร่อยกว่า", "1+1 ได้เท่าไหร่"]:
            k, _ = intent_model.classify(q, use_llm=False)
            self.assertEqual(k, "out_of_domain", q)

    def test_question_does_not_extract_values(self):
        from app.flows.chat import _read_values
        self.assertEqual(_read_values("หมากับแมวอะไรน่ารักกว่า"), [])
        self.assertEqual(_read_values("แมวกับไก่ ตัวไหนอร่อยกว่า"), [])
