"""Conversation checks use temporary storage and mocked models; no external calls."""
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import handlers, intent, storage
from app.flows import advice
from pipelines.llm import prompts, tasks
from pipelines.retrieval.contract import RetrievalItem, RetrievalResult


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(storage, 'DB_PATH', Path(self.tmp.name) / 'test.db')
        self.db_patch.start()
        memory_patch = patch.object(tasks, "summarize_memory", return_value=[])
        memory_patch.start()
        self.addCleanup(memory_patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.db_patch.stop)

    def turn(self, uid='A', question='แฟนเงียบใส่ ควรทำยังไง', answer='ลองเริ่มคุยอย่างใจเย็น [1]', kind='ask_advice'):
        storage.add_message(uid, 'user', question, kind)
        storage.add_message(uid, 'bot', answer, kind)

    def history(self, uid='A', **kw):
        mid = storage.add_message(uid, 'user', 'ช่วยยกตัวอย่างหน่อย')
        return storage.advice_history(uid, mid, **kw)

    def test_complete_pairs_user_isolation_and_anchor(self):
        self.turn()
        self.turn('B', question='other user secret')
        mid = storage.add_message('A', 'user', 'current')
        storage.add_message('A', 'user', 'later request')
        h = storage.advice_history('A', mid)
        self.assertEqual([m['role'] for m in h], ['user', 'assistant'])
        self.assertNotIn('[1]', h[1]['text'])
        self.assertNotIn('secret', str(h))
        self.assertNotIn('current', str(h))
        self.assertNotIn('later request', str(h))

    def test_contact_and_other_flows_are_boundaries(self):
        for kind in ('contact', 'find_match', 'show_profile'):
            with self.subTest(kind=kind):
                uid = kind
                self.turn(uid)
                self.turn(uid, question='private information', kind=kind)
                self.assertEqual(self.history(uid), [])

    def test_budget_expiry_and_incomplete_turn(self):
        self.turn()
        self.assertEqual(self.history(max_tokens=1), [])
        self.turn('B')
        with storage.db() as c:
            c.execute('UPDATE messages SET ts=? WHERE user_id=?', (time.time()-3600, 'B'))
        self.assertTrue(self.history('B'))
        storage.add_message('C', 'user', 'unfinished', 'ask_advice')
        self.assertEqual(self.history('C'), [])

    def test_followup_and_explicit_commands(self):
        self.turn()
        h = self.history()
        for q in ('ช่วยยกตัวอย่างหน่อย', 'ขอรายละเอียดข้อสอง', 'แล้วถ้าเขายังทำแบบเดิมล่ะ'):
            self.assertEqual(intent.classify(q, history=h), 'ask_advice')
            self.assertEqual(intent.classify(q), 'chat')
        self.assertEqual(intent.classify('หาคู่ให้หน่อย', history=h), 'find_match')
        self.assertEqual(intent.classify('ลบข้อมูลของฉัน', history=h), 'delete_me')
        self.assertEqual(intent.classify('ช่วยยกตัวอย่างหน่อย', 'await_contact', h), 'contact')
        self.assertFalse(intent.is_followup('เปลี่ยนเรื่อง ขอรายละเอียดเรื่องใหม่'))
        self.assertFalse(intent.is_followup('ไปเที่ยวภูเขาควรเตรียมอะไร'))
        self.assertTrue(intent.is_followup('เขายังไม่ตอบเลย ควรทำยังไง'))

    def test_retrieval_uses_rewrite_answer_uses_original_and_history(self):
        from pipelines.hybrid.search import Found
        self.turn()
        h = self.history()
        item = RetrievalItem('chunk1', 'chunk', 'knowledge', 1.0, 'dense')
        result = RetrievalResult('hybrid', 'query', [item], 1.0)
        output = {'answer': 'คำตอบต่อเนื่อง [1]', 'refs': ['chunk1'], 'citations': {'cited': [1], 'abstained': False}}
        # ค้นผ่าน search.find (ค้น + ด่านความเกี่ยวข้อง + แปลงคำถาม) ด้วยคำถามที่แปลงจากประวัติแล้ว
        with patch.object(advice, '_retriever', SimpleNamespace()), \
             patch.object(advice.search, 'find', return_value=Found(result, 'dense', 1)) as find, \
             patch.object(tasks, 'rewrite_question', return_value='ตัวอย่างคุยกับแฟนที่เงียบใส่') as rewrite, \
             patch.object(tasks, 'rag_answer', return_value=output) as answer, \
             patch.object(advice, 'verify_answer', return_value=('คำตอบต่อเนื่อง [1]', 0)) as verify, \
             patch.object(advice.live, 'ctx', return_value=SimpleNamespace(graph=SimpleNamespace(prop=lambda *a: None))):
            advice.handle({}, 'ช่วยยกตัวอย่างหน่อย', history=h)
            rewrite.assert_called_once_with('ช่วยยกตัวอย่างหน่อย', h)
            self.assertEqual(find.call_args.args[1], 'ตัวอย่างคุยกับแฟนที่เงียบใส่')
            answer.assert_called_once_with('ช่วยยกตัวอย่างหน่อย', result, history=h)
            verify.assert_called_once_with('ตัวอย่างคุยกับแฟนที่เงียบใส่', 'คำตอบต่อเนื่อง [1]', ['knowledge'])
            rewrite.reset_mock()
            advice.handle({}, 'ทฤษฎีความรักคืออะไร', history=h)
            rewrite.assert_not_called()
            self.assertEqual(find.call_args.args[1], 'ทฤษฎีความรักคืออะไร')
            answer.assert_called_with('ทฤษฎีความรักคืออะไร', result, history=[])
            verify.assert_called_with('ทฤษฎีความรักคืออะไร', 'คำตอบต่อเนื่อง [1]', ['knowledge'])

    def test_missing_or_failed_rewrite_asks_for_clarification(self):
        with patch.object(tasks, 'rag_answer') as answer:
            self.assertIn('หมายถึงเรื่องไหน', advice.handle({}, 'แล้วควรทำยังไง')[0]['text'])
            with patch.object(tasks, 'rewrite_question', side_effect=tasks.AmbiguousFollowup):
                out = advice.handle({}, 'ช่วยยกตัวอย่างหน่อย', history=[{'role':'user','text':'old'}])
                self.assertIn('ระบุเรื่อง', out[0]['text'])
            answer.assert_not_called()

    def test_prompt_separates_history_and_current_evidence(self):
        h = [{'role':'user','text':'แฟนเงียบใส่'}, {'role':'assistant','text':'คำตอบเก่า'}]
        msgs = prompts.rag_messages('ยกตัวอย่าง', '[1] new evidence', history=h)
        self.assertEqual([m['role'] for m in msgs], ['system','user','assistant','user'])
        self.assertIn('ไม่ใช่หลักฐาน', msgs[0]['content'])
        self.assertIn('[1] new evidence', msgs[-1]['content'])
        self.assertEqual(len(prompts.rag_messages('question', 'context')), 2)

    def test_dispatch_carries_history_without_current_message(self):
        u = storage.create_line_user('line-A', 'A')
        storage.set_state('line-A', 'ready')
        self.turn(u['user_id'])
        with patch.object(advice, 'handle', return_value=[{'type':'text','text':'answer'}]) as handle:
            handlers.dispatch({'type':'message','source':{'userId':'line-A'},
                               'message':{'type':'text','text':'ช่วยยกตัวอย่างหน่อย'}})
        h = handle.call_args.kwargs['history']
        self.assertEqual(len(h), 2)
        self.assertNotIn('ช่วยยกตัวอย่างหน่อย', str(h))
        self.assertEqual(storage.recent_messages(u['user_id'], 1)[0]['text'], 'answer')

    def test_concurrent_requests_wait_for_previous_answer(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        u = storage.create_line_user('line-A', 'A')
        storage.set_state('line-A', 'ready')
        self.turn(u['user_id'])
        started, release = threading.Event(), threading.Event()
        seen = []

        def respond(user, msg, history=None):
            seen.append((msg, history))
            if msg == 'ขอรายละเอียดข้อสอง':
                started.set()
                if not release.wait(3):
                    raise RuntimeError('test timed out')
            return [{'type':'text', 'text':'answer: ' + msg}]

        def send(msg):
            return handlers.dispatch({'type':'message','source':{'userId':'line-A'},
                                      'message':{'type':'text','text':msg}})

        with patch.object(advice, 'handle', side_effect=respond), ThreadPoolExecutor(2) as pool:
            first = pool.submit(send, 'ขอรายละเอียดข้อสอง')
            self.assertTrue(started.wait(3))
            second = pool.submit(send, 'ช่วยยกตัวอย่างหน่อย')
            release.set()
            first.result(timeout=5)
            second.result(timeout=5)
        self.assertEqual(len(seen), 2)
        self.assertIn('answer: ขอรายละเอียดข้อสอง', str(seen[1][1]))

    def test_history_stops_at_new_standalone_topic(self):
        self.turn(question='แฟนเงียบใส่ ควรทำยังไง')
        self.turn(question='ความรักสามเหลี่ยมคืออะไร', answer='คำตอบเรื่องใหม่')
        h = self.history()
        self.assertEqual(len(h), 2)
        self.assertNotIn('แฟนเงียบใส่', str(h))

    def test_task_passes_history_to_provider_and_rejects_unknown(self):
        h = [{'role':'user','text':'แฟนเงียบใส่'}, {'role':'assistant','text':'คำตอบเก่า'}]
        result = RetrievalResult('hybrid', 'query', [RetrievalItem('c1','chunk','new evidence',1,'dense')])
        llm = SimpleNamespace(text='คำตอบ [1]', metrics={}, model='mock')
        with patch.object(tasks.providers, 'chat', return_value=llm) as chat:
            out = tasks.rag_answer('ขอตัวอย่าง', result, history=h)
            self.assertIn({'role':'assistant','content':'คำตอบเก่า'}, chat.call_args.args[1])
            self.assertEqual(out['refs'], ['c1'])
            llm.text = 'UNKNOWN'
            with self.assertRaises(ValueError):
                tasks.rewrite_question('ขอตัวอย่าง', h)

    def test_long_answer_retains_topic_and_recent_followup_within_budget(self):
        from pipelines.llm.context import estimate_tokens
        self.turn(question='แฟนเงียบใส่ ควรทำยังไง', answer='คำตอบยาวมาก ' * 3000)
        h = self.history()
        self.assertEqual(h[0]['text'], 'แฟนเงียบใส่ ควรทำยังไง')
        self.assertIn('[ตัดบางส่วน]', h[1]['text'])
        self.assertLessEqual(sum(estimate_tokens(m['text']) + 8 for m in h), 800)

    def test_topic_anchor_survives_several_followups(self):
        from pipelines.llm.context import estimate_tokens
        self.turn()
        for n in range(7):
            self.turn(question=f'ขอรายละเอียดข้อที่ {n}', answer='คำตอบยาว ' * 400)
        h = self.history()
        self.assertIn('แฟนเงียบใส่', h[0]['text'])
        self.assertIn('ข้อที่ 6', h[-2]['text'])
        self.assertLessEqual(sum(estimate_tokens(m['text']) + 8 for m in h), 800)

    def test_chat_narrative_and_acknowledgement_keep_context(self):
        self.turn(question='แฟนไม่คุยกับฉันมาสามวัน', answer='ฟังดูอึดอัดนะครับ', kind='chat')
        self.turn(question='ใช่เลย', answer='ผมเข้าใจครับ', kind='chat')
        h = self.history()
        self.assertIn('สามวัน', str(h))
        self.assertEqual(intent.classify('แล้วควรทำยังไง', history=h), 'ask_advice')

    def test_explicit_age_filter_is_optional_and_contacts_are_redacted(self):
        self.turn(question='แฟนเงียบใส่ LINE ID: private123 email: test@example.com ควรทำไง',
                  answer='ดู https://line.me/ti/p/private')
        h = self.history()
        for secret in ('private123', 'test@example.com', 'line.me'):
            self.assertNotIn(secret, str(h))
        self.turn('B')
        with storage.db() as c:
            c.execute('UPDATE messages SET ts=? WHERE user_id=?', (time.time()-3600, 'B'))
        self.assertEqual(self.history('B', max_age_s=1800), [])

    def test_provider_failure_does_not_claim_missing_memory(self):
        with patch.object(tasks, 'rewrite_question', side_effect=RuntimeError('offline')):
            out = advice.handle({}, 'ช่วยยกตัวอย่างหน่อย', history=[{'role':'user','text':'แฟนเงียบใส่'}])
        self.assertIn('ประมวลผล', out[0]['text'])
        self.assertNotIn('ระบุเรื่อง', out[0]['text'])

    def test_deletion_removes_history(self):
        u = storage.create_line_user('line-A', 'A')
        self.turn(u['user_id'])
        storage.delete_user('line-A')
        self.assertEqual(storage.recent_messages(u['user_id'], 20), [])


if __name__ == '__main__':
    unittest.main()
