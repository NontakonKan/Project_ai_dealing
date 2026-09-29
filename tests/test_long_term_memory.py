"""Persistent memory and retrieval tests: isolated DB, no real LLM calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import conversation, handlers, intent, storage
from pipelines.llm import tasks


class MemoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = patch.object(storage, 'DB_PATH', Path(tmp.name) / 'memory.db')
        db.start()
        self.addCleanup(db.stop)
        self.user = storage.create_line_user('line-a', 'A')
        self.uid = self.user['user_id']
        storage.set_state('line-a', 'ready')

    def message(self, text, uid=None, kind='chat'):
        return storage.add_message(uid or self.uid, 'user', text, kind)

    def change(self, sid, evidence, summary=None, operation='set'):
        return dict(key='preference.faculty', summary=summary or evidence, evidence=evidence,
                    source_id=sid, operation=operation)

    def update(self, sid, changes):
        with patch.object(tasks, 'summarize_memory', return_value=changes):
            conversation.refresh(self.uid, sid + 1)

    def test_persists_and_replaces_with_revision_and_source(self):
        a = self.message('ชอบคนเรียนวิศวะ')
        self.update(a, [self.change(a, 'ชอบคนเรียนวิศวะ')])
        b = self.message('ตอนนี้ไม่จำกัดคณะแล้ว')
        self.update(b, [self.change(b, 'ตอนนี้ไม่จำกัดคณะแล้ว')])
        facts = storage.memory_facts(self.uid)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]['source_id'], b)
        self.assertIn('ไม่จำกัด', facts[0]['summary'])
        with storage.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM conversation_memory_revisions').fetchone()[0], 2)
        self.assertEqual(storage.memory_facts('other'), [])

    def test_hallucinated_evidence_rejected_without_checkpoint(self):
        sid = self.message('ชอบคนเรียนวิศวะ')
        with self.assertRaises(ValueError):
            self.update(sid, [self.change(sid, 'เรียนแพทย์')])
        self.assertEqual(storage.memory_facts(self.uid), [])
        rows, checkpoint = storage.memory_pending(self.uid, sid+1)
        self.assertEqual(checkpoint, 0)
        self.assertEqual(len(rows), 1)

    def test_cross_user_source_rejected(self):
        self.message('ชอบวิศวะ')
        sid = self.message('ชอบหมอ', uid='B')
        with self.assertRaises(ValueError):
            self.update(sid, [self.change(sid, 'ชอบหมอ')])

    def test_outage_preserves_memory_and_retry_cursor(self):
        a = self.message('ชอบวิศวะ')
        self.update(a, [self.change(a, 'ชอบวิศวะ')])
        b = self.message('ไม่จำกัดคณะแล้ว')
        with patch.object(tasks, 'summarize_memory', side_effect=RuntimeError('offline')):
            conversation.prepare(self.uid, 'ไม่จำกัดคณะแล้ว', b, [])
        self.assertEqual(storage.memory_facts(self.uid)[0]['source_id'], a)
        self.assertEqual(storage.memory_pending(self.uid,b+1)[1], a)

    def test_archive_retrieves_outside_recent_window(self):
        old = self.message('เคยมีปัญหากับแฟนเรื่องการแบ่งค่าเช่าห้อง')
        for _ in range(35):
            self.message('วันนี้ทำอาหารกินเอง')
            storage.add_message(self.uid,'bot','รับทราบ','chat')
        ctx = conversation.context(self.uid,'ครั้งก่อนเล่าเรื่องค่าเช่าห้องว่าอะไร',99999,budget=1000)
        self.assertTrue(any(x.get('source_message_id') == old for x in ctx))
        self.assertEqual(conversation.context('B','ค่าเช่าห้อง',99999), [])

    def test_sensitive_and_contact_flow_excluded(self):
        self.message('LINE ID: secret-id', kind='contact')
        self.message('เป็นมุสลิม')
        sid = self.message('email: secret@example.com')
        with patch.object(tasks,'summarize_memory') as model:
            conversation.refresh(self.uid,sid+1)
            model.assert_not_called()
        self.assertEqual(storage.memory_facts(self.uid), [])
        self.assertEqual(conversation.context(self.uid,'จำได้ไหม',sid+1), [])

    def test_delete_user_removes_summary_revisions_and_cursor(self):
        sid = self.message('ชอบวิศวะ')
        self.update(sid,[self.change(sid,'ชอบวิศวะ')])
        storage.delete_user('line-a')
        with storage.db() as c:
            for table in ('messages','conversation_memory','conversation_memory_state','conversation_memory_revisions'):
                self.assertEqual(c.execute(f'SELECT count(*) FROM {table} WHERE user_id=?',(self.uid,)).fetchone()[0],0)

    def test_recall_route_does_not_use_knowledge_retriever(self):
        sid = self.message('ชอบวิศวะ')
        self.update(sid,[self.change(sid,'ชอบวิศวะ')])
        self.assertEqual(intent.classify('จำได้ไหมว่าชอบคณะอะไร'),'recall_memory')
        with patch.object(tasks,'recall_answer',return_value='คุณเคยบอกว่าชอบวิศวะ') as answer, \
             patch.object(tasks,'summarize_memory',return_value=[]), \
             patch('app.flows.advice.handle') as rag:
            out = handlers.dispatch({'type':'message','source':{'userId':'line-a'},
                                     'message':{'type':'text','text':'จำได้ไหมว่าชอบคณะอะไร'}})
            self.assertIn('วิศวะ',out[0]['text'])
            answer.assert_called_once()
            rag.assert_not_called()

    def test_archived_assistant_details_are_labelled_not_facts(self):
        sid = self.message('ค่าเช่าห้องควรแบ่งยังไง', kind='ask_advice')
        rid = storage.add_message(self.uid,'bot','ข้อสอง แบ่งค่าเช่าห้องตามรายได้','ask_advice')
        ctx = conversation.context(self.uid,'ครั้งก่อนเรื่องค่าเช่าห้องข้อสองคืออะไร',rid+1,budget=1000)
        self.assertTrue(any(x.get('kind') == 'historical_assistant_not_evidence'
                            and x['source_message_id'] == rid for x in ctx))

    def test_delete_operation_removes_active_fact(self):
        sid = self.message('ชอบวิศวะ')
        self.update(sid,[self.change(sid,'ชอบวิศวะ')])
        sid2 = self.message('ลืมความชอบคณะเดิม')
        self.update(sid2,[self.change(sid2,'ลืมความชอบคณะเดิม',operation='delete')])
        self.assertEqual(storage.memory_facts(self.uid), [])

    def test_latest_correction_is_included_on_large_backlog(self):
        for i in range(20):
            self.message(f'เล่าเรื่องเก่า {i}')
        sid = self.message('ตอนนี้ไม่จำกัดคณะแล้ว')
        with patch.object(tasks,'summarize_memory',return_value=[self.change(sid,'ตอนนี้ไม่จำกัดคณะแล้ว')]) as model:
            conversation.refresh(self.uid,sid+1)
        self.assertEqual(model.call_args.args[0][-1]['id'],sid)
        self.assertEqual(storage.memory_facts(self.uid)[0]['source_id'],sid)

    def test_stale_checkpoint_cannot_overwrite_new_memory(self):
        sid = self.message('ชอบวิศวะ')
        rows, checkpoint = storage.memory_pending(self.uid,sid+1)
        changes = [self.change(sid,'ชอบวิศวะ')]
        self.assertTrue(storage.apply_memory(self.uid,changes,rows,checkpoint,sid))
        self.assertFalse(storage.apply_memory(self.uid,changes,rows,checkpoint,sid))

if __name__ == '__main__':
    unittest.main()
