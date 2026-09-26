"""follow -> ขอความยินยอม -> เพศ -> เพศที่สนใจ -> อายุ -> คณะ -> พร้อมคุย"""
from .. import live, storage
from ..flex import MENU, postback_quick, text
from ..profile import GENDER
from .common import load, save

SEEKING = {"ชาย": ["M"], "หญิง": ["F"], "ทุกเพศ": ["M", "F", "NB"]}
WELCOME = ("สวัสดีครับ ผม \"น้องดีล\" ผู้ช่วยหาคู่ของชาว ม.อ. 💞\n"
           "คุยเล่นกับผมเรื่องชีวิตประจำวัน งานอดิเรก หรือสเปกที่ชอบได้เลย ผมจะจำไว้เพื่อหาคนที่เข้ากับคุณ\n\n"
           "🔒 ก่อนเริ่ม: บทสนทนาจะถูกใช้สร้างโปรไฟล์เพื่อจับคู่ อีกฝ่ายจะไม่เห็นสิ่งที่คุณเล่าให้ผมฟัง "
           "และคุณขอดูหรือลบข้อมูลได้ทุกเมื่อ ยินยอมไหมครับ?")


def follow(line_user):
    storage.set_state(line_user["line_user_id"], "onboard_consent")
    return [postback_quick(WELCOME, [("ยินยอม ✅", "action=consent&v=yes"), ("ยังไม่ยินยอม", "action=consent&v=no")])]


def consent(line_user, yes: bool):
    p = load(line_user)
    p["consent"]["matching"] = yes
    save(p)
    if not yes:
        storage.set_state(line_user["line_user_id"], "ready")
        return [text("ได้เลยครับ 🙂 ยังคุยเล่นหรือปรึกษาเรื่องความรักกับผมได้ตามปกติ ถ้าเปลี่ยนใจอยากให้ช่วยหาคู่ บอกผมได้เลยนะครับ",
                     MENU[1:])]
    storage.set_state(line_user["line_user_id"], "onboard_gender")
    return [text("ขอบคุณครับ 🙏 ขอรู้จักนิดนึงนะครับ คุณเป็น…", [(g, g) for g in GENDER])]


def unfollow(line_user):
    p = load(line_user)
    p["consent"]["matching"] = False   # บล็อก OA = หลุดจาก pool ทันที
    save(p)
    return []


def answer(line_user, msg):
    state, p = line_user["state"], load(line_user)
    uid = line_user["line_user_id"]
    if state == "onboard_consent":
        return follow(line_user)
    if state == "onboard_gender":
        if msg not in GENDER:
            return [text("เลือกจากปุ่มด้านล่างได้เลยครับ", [(g, g) for g in GENDER])]
        p["demographic"]["gender"] = GENDER[msg]
        save(p)
        storage.set_state(uid, "onboard_seeking")
        return [text("สนใจคุยกับ…", [(s, s) for s in SEEKING])]
    if state == "onboard_seeking":
        if msg not in SEEKING:
            return [text("เลือกจากปุ่มด้านล่างได้เลยครับ", [(s, s) for s in SEEKING])]
        p["demographic"]["seeking"] = SEEKING[msg]
        save(p)
        storage.set_state(uid, "onboard_age")
        return [text("อายุเท่าไหร่ครับ (พิมพ์ตัวเลข)")]
    if state == "onboard_age":
        digits = "".join(ch for ch in msg if ch.isdigit())
        if not digits or not 18 <= int(digits) <= 40:
            return [text("ขอเป็นตัวเลขอายุ 18–40 ปีนะครับ")]
        p["demographic"]["age"] = int(digits)
        save(p)
        storage.set_state(uid, "onboard_faculty")
        return [text("เรียนคณะอะไรครับ?")]
    if state == "onboard_faculty":
        p["demographic"]["faculty"] = msg.strip()[:40]
        save(p)
        storage.set_state(uid, "ready")
        live.register(p)
        from .. import log
        d = p["demographic"]
        log.note(f"✅ ลงทะเบียนเสร็จ {d['gender']}→{d['seeking']} อายุ {d['age']} {d['faculty']} (เข้า pool จับคู่แล้ว)")
        return [text("เรียบร้อยครับ 🎉 ตอนนี้เล่าเรื่องวันนี้ งานอดิเรก หรือสเปกที่ชอบให้ผมฟังได้เลย "
                     "ยิ่งเล่ามาก ยิ่งหาคนที่เข้ากันได้แม่นขึ้นครับ", MENU)]
    return []
