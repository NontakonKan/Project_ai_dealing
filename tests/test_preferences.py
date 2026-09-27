"""คณะที่อยากได้ + ค่านิยมใหม่ + ความยินยอมข้อมูลอ่อนไหว (ไม่ต้องเปิด Ollama/LINE)

python -m unittest discover -s tests
"""
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("APP_DB", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = ""

from app.flows.match import extra_reasons  # noqa: E402
from app.profile import describe, merge_faculty, merge_values, new_profile, set_sensitive_consent  # noqa: E402
from pipelines.hybrid.context import HybridContext  # noqa: E402
from pipelines.profile import faculty  # noqa: E402


def _user(uid, fac, fac_wants=()):
    p = new_profile(uid, uid)
    p["demographic"]["faculty"] = fac
    p["preferences"]["faculty_wants"] = list(fac_wants)
    return p


class FacultyTests(unittest.TestCase):
    def test_parse_self_vs_partner(self):
        self.assertEqual(faculty.parse("ชอบผู้หญิงเรียน วิศวะ")["wants"], ["วิศวกรรมศาสตร์"])
        r = faculty.parse("ผมเรียนวิศวะ อยากได้แฟนเป็นหมอ")
        self.assertEqual((r["self"], r["wants"]), ("วิศวกรรมศาสตร์", ["แพทยศาสตร์"]))
        self.assertEqual(faculty.parse("อยากได้แฟนแพทย์แผนไทย")["wants"], ["การแพทย์แผนไทย"])   # ไม่ใช่ "แพทยศาสตร์"

    def test_no_false_positive(self):
        for t in ("พยายามเรียนที่มหาวิทยาลัย", "วันนี้ไปหาหมอมา", "ชอบทำอาหาร"):
            self.assertEqual(faculty.parse(t)["spans"], [], t)

    def test_merge_and_score(self):
        me = _user("A", "วิศวะ")
        merge_faculty(me, faculty.parse("ชอบผู้หญิงเรียนวิศวะ"))
        ctx = SimpleNamespace(users={"A": me, "B": _user("B", "วิศวกรรมศาสตร์"), "C": _user("C", "วิทยาศาสตร์")},
                              values_struct={})
        self.assertEqual(HybridContext.faculty_sim(ctx, "A", "B"), 1.0)
        self.assertEqual(HybridContext.faculty_sim(ctx, "A", "C"), 0.0)
        self.assertIn("วิศวกรรมศาสตร์", extra_reasons(ctx, "A", "B")[0])


class SensitiveValuesTests(unittest.TestCase):
    def test_pending_until_consent(self):
        p = new_profile("A", "A")
        ask = merge_values(p, {"self": {"religion": "muslim", "drinking": "no_drink"}}, "เป็นมุสลิม ไม่ดื่ม")
        self.assertTrue(ask)
        self.assertEqual(p["values"]["self"], {"drinking": "no_drink"})       # อ่อนไหวยังไม่ถูกใช้
        self.assertEqual(p["values"]["self_text"], [])                        # ประโยคที่มีศาสนาไม่ถูกเก็บเป็นข้อความ
        set_sensitive_consent(p, True)
        self.assertEqual(p["values"]["self"]["religion"], "muslim")
        self.assertIn("🔒", describe(p))

    def test_decline_drops(self):
        p = new_profile("A", "A")
        merge_values(p, {"wants": {"diet": "halal"}}, "อยากได้คนกินฮาลาล")
        set_sensitive_consent(p, False)
        self.assertNotIn("diet", p["values"]["wants"])
        self.assertFalse(merge_values(p, {"wants": {"diet": "halal"}}, "กินฮาลาล"))   # ไม่ยินยอมแล้ว = ไม่ถามซ้ำ ไม่เก็บ
        self.assertNotIn("diet", p["values"]["wants"])

    def test_card_never_shows_sensitive(self):
        a, b = _user("A", "x"), _user("B", "y")
        ctx = SimpleNamespace(users={"A": a, "B": b}, values_struct={
            "A": {"self": {}, "wants": {"religion": "muslim", "drinking": "no_drink"}},
            "B": {"self": {"religion": "muslim", "drinking": "no_drink"}, "wants": {}}})
        text = " ".join(extra_reasons(ctx, "A", "B"))
        self.assertIn("ไม่ดื่มเหล้า", text)
        self.assertNotIn("อิสลาม", text)


if __name__ == "__main__":
    unittest.main()
