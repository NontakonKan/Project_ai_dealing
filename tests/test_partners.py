"""ประวัติคู่ (app/flows/partners.py): ตอนนี้คุยกับใคร + เป้าหมายของ "เลิกคุย" เมื่อพิมพ์เอง — DB แยกชั่วคราว

python -m unittest discover -s tests
"""
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import storage
from app.flows import partners, unmatch

USERS = {x: {"user_id": x, "display_name": n, "demographic": {"faculty": "วิศวกรรมศาสตร์"}, "persona": {}}
         for x, n in (("L0001", "เอ"), ("M001", "มายด์"), ("M002", "บีม"), ("M003", "ฟ้า"), ("L0002", "ต้น"))}


class PartnerHistoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (patch.object(storage, "DB_PATH", Path(tmp.name) / "p.db"),
                  patch.object(partners.live, "ctx", lambda: SimpleNamespace(users=USERS))):
            p.start()
            self.addCleanup(p.stop)
        self.u = storage.create_line_user("line-a", "เอ")
        self.uid = self.u["user_id"]

    def _event(self, etype, about, ts):
        with storage.db() as c:
            c.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (f"E{ts}{about}", etype, self.uid, about, "{}", ts))

    def _suggest(self, cid, ts):
        with storage.db() as c:
            c.execute("INSERT INTO suggestions VALUES (?,?,?,?)", (self.uid, cid, 0.5, ts))

    def test_accepted_intro_is_current_even_if_newer_suggestion(self):
        now = time.time()
        storage.create_intro("IN1", self.uid, "L0002")
        storage.decide_intro("IN1", "accepted")
        self._event("matched", "L0002", now)          # _finalize เขียน matched ซ้ำ -> ต้องยังเป็น talking
        self._suggest("M001", now + 10)
        self.assertEqual(partners.current(self.uid)["user_id"], "L0002")
        rows = {x["user_id"]: x["status"] for x in partners.history(self.uid)}
        self.assertEqual(rows, {"L0002": "talking", "M001": "suggested"})

    def test_newer_unmatch_closes_the_partner(self):
        now = time.time()
        self._suggest("M001", now)
        self._event("matched", "M001", now + 1)
        self.assertEqual(partners.current(self.uid)["status"], "interested")
        self._event("unmatch", "M001", now + 2)
        self.assertIsNone(partners.current(self.uid))
        self.assertEqual(partners.history(self.uid)[0]["status"], "unmatched")

    def test_unmatch_targets_the_person_being_talked_to(self):
        now = time.time()
        self._suggest("M001", now)                     # ลำดับตัวอักษรมาก่อน แต่ไม่ได้คุยกันจริง
        self._suggest("M003", now + 1)
        self._event("matched", "M003", now + 2)
        line_user = storage.get_line_user("line-a")
        out = unmatch.ask_reason(line_user)
        self.assertIn("ฟ้า", out[0]["text"])
        self.assertEqual(storage.get_line_user("line-a")["state_data"]["target"], "M003")

    def test_several_active_partners_asks_which_one(self):
        now = time.time()
        for i, cid in enumerate(("M001", "M002")):
            self._event("matched", cid, now + i)
        out = unmatch.ask_reason(storage.get_line_user("line-a"))
        datas = [it["action"]["data"] for it in out[0]["quickReply"]["items"]]
        self.assertEqual(datas, ["action=unmatch&target=M002", "action=unmatch&target=M001"])
        self.assertNotEqual(storage.get_line_user("line-a")["state"], "await_unmatch_reason")

    def test_delete_removes_intros(self):
        storage.create_intro("IN2", self.uid, "L0002")
        storage.delete_user("line-a")
        self.assertEqual(storage.interactions(self.uid)["intros"], [])


if __name__ == "__main__":
    unittest.main()
