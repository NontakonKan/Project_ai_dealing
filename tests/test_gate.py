"""กฎของด่านกันหลอนที่ไม่ต้องโหลดโมเดล (pipelines/hybrid/gate.py)

python -m unittest discover -s tests
"""
import unittest

from pipelines.hybrid.gate import _is_echo, _windows


class EchoTests(unittest.TestCase):
    def test_pure_echo_is_caught(self):
        self.assertTrue(_is_echo("จีบรุ่นพี่ในคณะดีไหม", "จีบรุ่นพี่ในคณะดีไหม"))

    def test_short_factual_answers_are_kept(self):
        self.assertFalse(_is_echo("งานวิจัยนี้มีกลุ่มตัวอย่าง 433 คน", "งานวิจัยนี้มีกลุ่มตัวอย่างกี่คน"))
        self.assertFalse(_is_echo("ทฤษฎีความรักสามเหลี่ยมทำให้เกิดรูปแบบความรัก 8 แบบ",
                                  "ทฤษฎีความรักสามเหลี่ยมทำให้เกิดรูปแบบความรักกี่แบบ"))
        self.assertFalse(_is_echo("การเปิดเผยความสัมพันธ์ต่อเพื่อนมีความเกี่ยวข้องกับความพึงพอใจ",
                                  "การเปิดเผยความสัมพันธ์ต่อเพื่อนเกี่ยวข้องกับความพึงพอใจไหม"))


class WindowTests(unittest.TestCase):
    def test_long_passage_tail_is_covered(self):
        text = "ก" * 1500 + "ส่วนท้ายที่ตอบคำถาม"
        self.assertTrue(any("ส่วนท้ายที่ตอบคำถาม" in w for w in _windows(text)))

    def test_short_passage_single_window(self):
        self.assertEqual(_windows("สั้นๆ"), ["สั้นๆ"])



class PartnerTermTests(unittest.TestCase):
    def test_partner_words_expand(self):
        from pipelines.hybrid.query_expand import variants
        self.assertIn("แฟนเงียบควรทำอย่างไร", variants("คนคุยเงียบควรทำอย่างไร"))
        self.assertIn("จะรู้ได้ไงว่าอีกฝ่ายสนใจเรา", variants("จะรู้ได้ไงว่าเค้าสนใจเรา"))
        self.assertEqual(variants("Gaslighting คืออะไร"), ["Gaslighting คืออะไร"])

    def test_friend_kept_when_partner_present(self):
        from pipelines.hybrid.query_expand import variants
        for v in variants("ถ้ามีนัดกับเพื่อนและแฟนวันเดียวกัน ควรทำอย่างไร"):
            self.assertIn("เพื่อน", v)     # ไม่เปลี่ยน "เพื่อน" เป็น "แฟน" จนความหมายเพี้ยน

class SlangTests(unittest.TestCase):
    def test_colloquial_words_expand(self):
        from pipelines.hybrid.query_expand import hint, variants
        self.assertIn("ควรเริ่มต้นความสัมพันธ์ยังไงดี", variants("ควรเริ่มทักยังไงดี"))
        self.assertIn("เริ่มต้นความสัมพันธ์", hint("ควรเริ่มทักยังไงดี"))

    def test_slang_only_whole_word(self):
        from pipelines.hybrid.query_expand import variants
        self.assertEqual(variants("ทักษะการสื่อสารสำคัญไหม"), ["ทักษะการสื่อสารสำคัญไหม"])   # "ทัก" ใน "ทักษะ" ไม่แทน


if __name__ == "__main__":
    unittest.main()
