"""ความโปร่งใส + สิทธิ์ของผู้ใช้: ดูสิ่งที่ระบบจำ / ลบข้อมูลทั้งหมด"""
from .. import live, storage
from ..flex import MENU, postback_quick, text
from ..profile import describe
from .common import load


def show(line_user):
    return [text(describe(load(line_user)), MENU)]


def confirm_delete(line_user):
    """ลบย้อนกลับไม่ได้ + เจตนามาจากการตีความความหมาย (อาจพลาด) -> ต้องกดยืนยันทุกครั้ง"""
    return [postback_quick("ต้องการลบข้อมูลทั้งหมดของคุณใช่ไหมครับ? 🗑️\n(โปรไฟล์ ความจำ ประวัติแชท และคู่ที่แนะนำ — ย้อนกลับไม่ได้)",
                           [("ยืนยันลบ", "action=delete&v=yes"), ("ยกเลิก", "action=delete&v=no")])]


def delete(line_user):
    uid = line_user["user_id"]
    storage.delete_user(line_user["line_user_id"])
    live.ctx().users.pop(uid, None)
    return [text("ลบข้อมูลทั้งหมดของคุณแล้วครับ 🗑️ ถ้าอยากเริ่มใหม่ ทักผมมาได้เสมอนะครับ")]
