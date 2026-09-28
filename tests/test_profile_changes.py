"""ผู้ใช้เปลี่ยนความชอบ -> โปรไฟล์ต้องแทนค่าเดิม ไม่ใช่เพิ่มต่อท้าย (app/profile.py)

python -m unittest discover -s tests
"""
import unittest

from app.profile import merge_extraction, merge_faculty, new_profile
from pipelines.profile import faculty


def wants(p):
    return [x["id"] for x in p["preferences"]["wants"]]


class ChangeMindTests(unittest.TestCase):
    def setUp(self):
        self.p = new_profile("L9", "t")
        merge_extraction(self.p, {"wants": [{"id": "skin:fair"}, {"id": "trait:logical"}]}, "อยากได้คนผิวขาว มีเหตุผล")

    def test_change_replaces_same_group(self):
        merge_extraction(self.p, {"wants": [{"id": "skin:dark"}]}, "เปลี่ยนใจชอบผิวดำ")     # เคสจริงจาก LINE
        self.assertIn("skin:dark", wants(self.p))
        self.assertNotIn("skin:fair", wants(self.p))
        self.assertIn("trait:logical", wants(self.p))        # กลุ่มอื่นไม่ถูกลบ

    def test_without_change_cue_keeps_both(self):
        merge_extraction(self.p, {"wants": [{"id": "skin:tan"}]}, "ผิวแทนก็ชอบนะ")
        self.assertEqual({"skin:fair", "skin:tan"} <= set(wants(self.p)), True)

    def test_tan_skin_word_is_not_a_change_cue(self):
        from app.profile import is_change
        self.assertFalse(is_change("ผิวแทนก็ชอบนะ"))
        self.assertTrue(is_change("อยากได้ผิวเข้มแทน"))

    def test_traits_are_not_exclusive(self):
        merge_extraction(self.p, {"wants": [{"id": "trait:calm"}]}, "เปลี่ยนใจ อยากได้คนใจเย็น")
        self.assertIn("trait:logical", wants(self.p))

    def test_avoid_removes_from_wants(self):
        merge_extraction(self.p, {"avoids": [{"id": "trait:logical"}]}, "ไม่ชอบคนมีเหตุผลแล้ว")
        self.assertNotIn("trait:logical", wants(self.p))
        self.assertIn("trait:logical", [x["id"] for x in self.p["preferences"]["avoids"]])

    def test_want_removes_from_avoids(self):
        merge_extraction(self.p, {"avoids": [{"id": "trait:funny"}]}, "ไม่ชอบคนตลก")
        merge_extraction(self.p, {"wants": [{"id": "trait:funny"}]}, "ตอนนี้ชอบคนตลกแล้ว")
        self.assertNotIn("trait:funny", [x["id"] for x in self.p["preferences"]["avoids"]])


class FacultyChangeTests(unittest.TestCase):
    def setUp(self):
        self.p = new_profile("L9", "t")
        t = "อยากได้คนเรียนแพทย์"
        merge_faculty(self.p, faculty.parse(t), t)

    def test_change_replaces_faculty(self):
        t = "เปลี่ยนใจ อยากได้คนเรียนวิศวะแทน"
        merge_faculty(self.p, faculty.parse(t), t)
        self.assertEqual(self.p["preferences"]["faculty_wants"], ["วิศวกรรมศาสตร์"])

    def test_adding_without_cue_keeps_both(self):
        t = "อยากได้คนเรียนนิติด้วย"
        merge_faculty(self.p, faculty.parse(t), t)
        self.assertEqual(set(self.p["preferences"]["faculty_wants"]), {"แพทยศาสตร์", "นิติศาสตร์"})

    def test_any_faculty_clears(self):
        t = "ไม่จำกัดคณะแล้ว"
        merge_faculty(self.p, faculty.parse(t), t)
        self.assertEqual(self.p["preferences"]["faculty_wants"], [])


if __name__ == "__main__":
    unittest.main()
