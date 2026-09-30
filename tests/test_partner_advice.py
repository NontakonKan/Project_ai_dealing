"""คำปรึกษาที่ปรับตามคนคุย (app/flows/advice.py + partners.talking_to)

- ปรับเฉพาะตอน "อยู่ในช่วงคุยกัน" (แลก LINE ID / กดสนใจผู้ใช้จำลอง) นอกช่วงตอบแบบทั่วไป
- บรรทัดที่ปรับต้องอ้างอิงคำแนะนำในคลัง + พูดถึงลักษณะที่ให้ไปจริง ไม่งั้นทิ้ง

python -m unittest discover -s tests
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.flows import advice, partners
from pipelines.hybrid.search import Found
from pipelines.retrieval.contract import RetrievalItem, RetrievalResult
from pipelines.llm import tasks

PARTNER = {"user_id": "M001", "name": "มายด์", "facts": ["สุภาพ", "เล่นดนตรี"]}
PASSAGE = "การเริ่มต้นความสัมพันธ์ ควรชวนคุยเรื่องที่อีกฝ่ายสนใจและงานอดิเรก"
TAILORED = "👉 กับมายด์: ลองชวนคุยเรื่องดนตรีที่เขาเล่นอยู่ [1]"


def _run(answer, partner, verify=lambda q, a, p: (a, 0)):
    item = RetrievalItem("chunk1", "chunk", PASSAGE, 1.0, "dense")
    result = RetrievalResult("hybrid", "q", [item], 1.0)
    output = {"answer": answer, "refs": ["chunk1"], "citations": {"cited": [1], "abstained": False}}
    with patch.object(advice, "_retriever", SimpleNamespace()), \
         patch.object(advice.search, "find", return_value=Found(result, "dense", 1)), \
         patch.object(tasks, "rag_answer", return_value=output) as rag, \
         patch.object(advice, "verify_answer", side_effect=verify), \
         patch.object(partners, "talking_to", return_value=partner), \
         patch.object(advice.live, "ctx", return_value=SimpleNamespace(graph=SimpleNamespace(prop=lambda *a: None))):
        out = advice.handle({"user_id": "L0001"}, "ควรชวนคุยอะไรครั้งแรก", history=[])
    return out[0]["text"], rag.call_args.kwargs["partner"]


class PartnerAdviceTests(unittest.TestCase):
    def test_in_conversation_adds_verified_tailored_line(self):
        text, sent = _run("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]\n" + TAILORED, PARTNER)
        self.assertEqual(sent, PARTNER)
        self.assertIn("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]", text)
        self.assertIn("👉 กับมายด์:", text)
        self.assertIn("ดนตรี", text)

    def test_not_in_conversation_answers_generally(self):
        text, sent = _run("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]\n" + TAILORED, None)
        self.assertIsNone(sent)
        self.assertNotIn("👉", text)          # ไม่ได้คุยกับใคร -> ทิ้งบรรทัดปรับแม้โมเดลจะเขียนมา

    def test_tailored_line_about_invented_trait_is_dropped(self):
        text, _ = _run("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]\n👉 กับมายด์: ชวนเขาไปเล่นบาสด้วยกัน [1]", PARTNER)
        self.assertNotIn("บาส", text)
        self.assertIn("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน", text)

    def test_tailored_line_without_citation_is_dropped(self):
        text, _ = _run("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]\n👉 กับมายด์: ชวนคุยเรื่องดนตรี", PARTNER)
        self.assertNotIn("👉", text)

    def test_tailored_line_without_evidence_is_dropped(self):
        def verify(q, a, passages):
            return (None, 1) if "ดนตรี" in a else (a, 0)
        text, _ = _run("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]\n" + TAILORED, PARTNER, verify)
        self.assertNotIn("👉", text)
        self.assertIn("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน", text)

    def test_tailored_line_is_checked_against_passage_plus_traits(self):
        seen = []
        _run("ชวนคุยเรื่องที่อีกฝ่ายสนใจก่อน [1]\n" + TAILORED, PARTNER,
             lambda q, a, p: (seen.append(p), (a, 0))[1])
        self.assertIn(PASSAGE, seen[-1][0])
        self.assertIn("เล่นดนตรี", seen[-1][0])


class TalkingToTests(unittest.TestCase):
    USERS = {"M001": {"display_name": "มายด์", "persona": {"traits": [{"id": "t:polite"}], "hobbies": [{"id": "h:music"}],
                                                              "appearance": [{"id": "skin:dark"}]}}}
    LABELS = {"t:polite": "สุภาพ", "h:music": "เล่นดนตรี", "skin:dark": "ผิวเข้ม"}

    def _talking(self, status):
        with patch.object(partners, "current", return_value={"user_id": "M001", "status": status, "ts": 1}), \
             patch.object(partners.live, "ctx", return_value=SimpleNamespace(users=self.USERS)), \
             patch("pipelines.common.taxonomy.labels", return_value=self.LABELS):
            return partners.talking_to("L0001")

    def test_only_in_conversation_counts(self):
        for status in ("talking", "interested"):
            self.assertEqual(self._talking(status)["facts"], ["สุภาพ", "เล่นดนตรี"])
        for status in ("waiting_them", "waiting_you", "suggested"):
            self.assertIsNone(self._talking(status))

    def test_only_card_level_traits_are_shared(self):
        self.assertNotIn("ผิวเข้ม", self._talking("talking")["facts"])


if __name__ == "__main__":
    unittest.main()
