"""helper ที่ทุก flow ใช้: โหลด/บันทึกโปรไฟล์ + sync เข้า context ของ Hybrid"""
import uuid

from .. import live, storage
from ..profile import build_summaries, new_profile


def load(line_user):
    return storage.load_profile(line_user["user_id"]) or new_profile(line_user["user_id"], line_user["display_name"])


def save(profile):
    build_summaries(profile)
    storage.save_profile(profile)
    live.ctx()
    live.register(profile)


def event_id():
    return "LE" + uuid.uuid4().hex[:10]
