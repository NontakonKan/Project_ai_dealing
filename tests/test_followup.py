"""คำถามต่อเนื่อง vs คำถามใหม่ที่แค่ขึ้นต้นด้วย เขา/เธอ (app/intent.py, app/flows/advice.py)

python -m unittest discover -s tests
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import intent
from app.flows import advice
from pipelines.hybrid.search import Found
from pipelines.llm import tasks
from pipelines.retrieval.contract import RetrievalItem, RetrievalResult


class NeedsContextTests(unittest.TestCase):
    def test_pronoun_start_is_self_contained(self):
        self.assertTrue(intent.is_followup("เขาไม่ตอบแชท ทำไงดี"))      # ยังนับเป็นต่อเนื่องเมื่อมีประวัติ
        self.assertFalse(intent.needs_context("เขาไม่ตอบแชท ทำไงดี"))   # แต่ถามครั้งแรกได้

    def test_explicit_references_need_context(self):
        for q in ("แล้วควรทำยังไง", "ข้อสองหมายถึงอะไร", "ยกตัวอย่างหน่อย", "ที่บอกเมื่อกี้คืออะไร"):
            self.assertTrue(intent.needs_context(q), q)


class HistoryCleanupTests(unittest.TestCase):
    def test_no_info_reply_is_not_used_as_topic(self):
        h = [{"role": "user", "text": "เขาไม่ตอบแชท ทำไงดี"}, {"role": "assistant", "text": advice.NO_INFO}]
        cleaned = advice._usable_history(h)
        self.assertEqual(cleaned[0], h[0])
        self.assertNotIn("ทฤษฎีความรัก", cleaned[1]["text"])


class FirstQuestionTests(unittest.TestCase):
    def test_pronoun_question_without_history_is_answered(self):
        item = RetrievalItem("chunk1", "chunk", "knowledge", 1.0, "dense")
        result = RetrievalResult("hybrid", "q", [item], 1.0)
        output = {"answer": "คำตอบ [1]", "refs": ["chunk1"], "citations": {"cited": [1], "abstained": False}}
        with patch.object(advice, "_retriever", SimpleNamespace()), \
             patch.object(advice.search, "find", return_value=Found(result, "dense", 1)) as find, \
             patch.object(tasks, "rewrite_question") as rewrite, \
             patch.object(tasks, "rag_answer", return_value=output), \
             patch.object(advice, "verify_answer", return_value=("คำตอบ [1]", 0)), \
             patch.object(advice.live, "ctx", return_value=SimpleNamespace(graph=SimpleNamespace(prop=lambda *a: None))):
            out = advice.handle({}, "เขาไม่ตอบแชท ทำไงดี", history=[])
        rewrite.assert_not_called()
        self.assertEqual(find.call_args.args[1], "เขาไม่ตอบแชท ทำไงดี")
        self.assertNotIn("หมายถึงเรื่องไหน", out[0]["text"])


if __name__ == "__main__":
    unittest.main()
