"""ความโปร่งใส + สิทธิ์ของผู้ใช้: ดูสิ่งที่ระบบจำ / ลบข้อมูลทั้งหมด"""
from .. import live, storage
from ..flex import MENU, text
from ..profile import describe
from .common import load


def show(line_user):
    return [text(describe(load(line_user)), MENU)]


def delete(line_user):
    uid = line_user["user_id"]
    storage.delete_user(line_user["line_user_id"])
    live.ctx().users.pop(uid, None)
    return [text("ลบข้อมูลทั้งหมดของคุณแล้วครับ 🗑️ ถ้าอยากเริ่มใหม่ ทักผมมาได้เสมอนะครับ")]
