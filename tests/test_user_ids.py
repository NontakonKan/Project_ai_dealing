"""เลขผู้ใช้ไม่ซ้ำหลังลบข้อมูล (app/storage.py) — DB แยกชั่วคราว

python -m unittest discover -s tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage


class UserIdTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = patch.object(storage, "DB_PATH", Path(tmp.name) / "ids.db")
        db.start()
        self.addCleanup(db.stop)

    def test_delete_then_new_user_does_not_collide(self):
        a = storage.create_line_user("line-a", "A")
        b = storage.create_line_user("line-b", "B")
        storage.delete_user("line-a")
        c = storage.create_line_user("line-c", "C")          # เดิม: IntegrityError (ได้ L0002 ซ้ำกับ b)
        self.assertNotIn(c["user_id"], {a["user_id"], b["user_id"]})

    def test_same_person_can_register_again(self):
        first = storage.create_line_user("line-a", "A")
        storage.delete_user("line-a")
        again = storage.create_line_user("line-a", "A")     # ลบแล้วทักใหม่ = โปรไฟล์ใหม่ เลขใหม่
        self.assertNotEqual(first["user_id"], again["user_id"])

    def test_deleted_highest_id_is_not_reused(self):
        storage.create_line_user("line-a", "A")
        top = storage.create_line_user("line-b", "B")
        storage.delete_user("line-b")
        new = storage.create_line_user("line-c", "C")
        self.assertNotEqual(new["user_id"], top["user_id"])


if __name__ == "__main__":
    unittest.main()
