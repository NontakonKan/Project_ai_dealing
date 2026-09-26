"""ทำความรู้จักแบบยินยอมทั้งสองฝ่าย (mutual consent)

A กด "สนใจทำความรู้จัก" บนการ์ดของ B
  -> ระบบส่งการ์ดของ A ให้ B ประเมิน (ยังไม่มีช่องทางติดต่อของใคร)
  -> B ยินยอม : ทั้งคู่ได้ LINE ID ของกันและกัน
     B ไม่สะดวก: A ได้ข้อความสุภาพ ไม่ได้ข้อมูลของ B และระบบจะไม่แนะนำคู่นี้อีก
LINE API ให้ bot เห็น LINE ID ของผู้ใช้ไม่ได้ -> ขอให้ผู้ใช้ส่ง ID เอง (เก็บแยก ส่งต่อเฉพาะเมื่อยินยอมทั้งคู่)
"""
import re

from graph import scorer

from .. import line_api, live, storage
from ..flex import MENU, request_card, text
from .common import event_id, load

RE_ID = re.compile(r"^@?[A-Za-z0-9._-]{4,20}$")
RE_LINK = re.compile(r"https?://line\.me/(?:ti/p|R/ti/p)/\S+")
ASK_CONTACT = ("ขอ LINE ID ของคุณหน่อยครับ (หรือวางลิงก์เพิ่มเพื่อนของคุณ)\n"
               "🔒 ผมจะส่งให้อีกฝ่าย \"เฉพาะเมื่อทั้งคู่ยินยอม\" เท่านั้น")
SAFETY = "💡 นัดเจอครั้งแรกแนะนำที่สาธารณะ และบอกเพื่อนสนิทไว้ด้วยนะครับ"


def _link(contact):
    return contact if contact.startswith("http") else f"https://line.me/ti/p/~{contact.lstrip('@')}"


def _you(fact):
    if fact.startswith("A อยากได้คนที่"):
        return fact.replace("A อยากได้คนที่", "คุณอยากได้คนที่")
    if fact.startswith("B อยากได้คนที่"):
        return fact.replace("B อยากได้คนที่", "อีกฝ่ายอยากได้คนที่").replace("— อีกฝ่ายมีนิสัยนี้", "— ตรงกับนิสัยของคุณ")
    return fact


def request(line_user, target):
    a, c = load(line_user), live.ctx()
    b = c.users.get(target)
    if not b:
        return [text("ไม่พบผู้ใช้คนนี้แล้วครับ", MENU)]
    prev = storage.find_intro(a["user_id"], target)
    if prev and prev["status"] == "pending":
        return [text("ส่งคำขอไปแล้วครับ รออีกฝ่ายตอบอยู่นะครับ ⏳")]
    if b.get("source") != "line":   # ผู้ใช้จำลอง: ไม่มีคนจริงมาตอบ
        live.add_event({"event_id": event_id(), "type": "matched", "from_user": a["user_id"], "about_user": target})
        return [text("🎉 บันทึกความสนใจแล้วครับ (คนนี้เป็นผู้ใช้จำลองสำหรับทดสอบ จึงไม่มีคนจริงมาตอบรับ) "
                     "ถ้ามีผู้ใช้จริงที่เข้ากับคุณ ผมจะส่งคำขอให้เขาประเมินก่อนแลกช่องทางติดต่อครับ", MENU)]
    if not storage.get_contact(a["user_id"]):
        storage.set_state(line_user["line_user_id"], "await_contact", {"then": "request", "target": target})
        return [text(ASK_CONTACT)]
    return _send_request(a, b)


def _send_request(a, b):
    intro_id = "IN" + event_id()[2:]
    storage.create_intro(intro_id, a["user_id"], b["user_id"])
    info = scorer.pair(live.ctx().graph, b["user_id"], a["user_id"], facts=True)   # มุมมองของ B
    reasons = [_you(f["text"]) for f in info["facts"] if not f["text"].startswith("⚠️")][:3] or ["ไลฟ์สไตล์ใกล้เคียงกัน"]
    pct = max(50, round(100 * min(1.0, info["graph_score"] / 0.8)))
    b_line = storage.line_id_of(b["user_id"])
    if b_line:
        line_api.push(b_line, [request_card(a, intro_id, pct, reasons)])
    return [text("ส่งคำขอทำความรู้จักให้อีกฝ่ายประเมินแล้วครับ 💌\n"
                 "ถ้าเขายินยอม ผมจะส่ง LINE ID ให้ทั้งสองฝ่ายทันที ถ้าไม่สะดวก ข้อมูลของคุณจะไม่ถูกส่งไปครับ", MENU)]


def decide(line_user, intro_id, accept: bool):
    b = load(line_user)
    req = storage.get_intro(intro_id)
    if not req or req["to_user"] != b["user_id"]:
        return [text("คำขอนี้ไม่มีอยู่แล้วครับ")]
    if req["status"] != "pending":
        return [text("คุณตอบคำขอนี้ไปแล้วครับ 🙂")]
    if not accept:
        storage.decide_intro(intro_id, "declined")
        live.add_event({"event_id": event_id(), "type": "pass", "from_user": b["user_id"], "about_user": req["from_user"]})
        a_line = storage.line_id_of(req["from_user"])
        if a_line:
            line_api.push(a_line, [text("ครั้งนี้อีกฝ่ายยังไม่สะดวกทำความรู้จักนะครับ 🙏 ไม่ใช่เรื่องผิดของใคร "
                                        "ผมจะไม่แนะนำคู่นี้อีก แล้วมาหาคนที่ใช่กันต่อครับ", [("หาคนใหม่", "หาคู่ให้หน่อย")])])
        return [text("รับทราบครับ 👌 อีกฝ่ายจะไม่ได้ข้อมูลใดๆ ของคุณ และผมจะไม่แนะนำคนนี้ให้คุณอีก", MENU)]
    if not storage.get_contact(b["user_id"]):
        storage.set_state(line_user["line_user_id"], "await_contact", {"then": "accept", "req": intro_id})
        return [text("ยินดีด้วยครับ 🎉 " + ASK_CONTACT)]
    return _finalize(req)


def _finalize(req):
    storage.decide_intro(req["id"], "accepted")
    a_id, b_id = req["from_user"], req["to_user"]
    for x, y in ((a_id, b_id), (b_id, a_id)):
        live.add_event({"event_id": event_id(), "type": "matched", "from_user": x, "about_user": y})
    users = live.ctx().users
    msg = lambda other: (f"🎉 ยินยอมทั้งสองฝ่ายแล้วครับ! เพิ่มเพื่อน {users[other].get('display_name') or ''} ได้เลย\n"
                         f"LINE: {_link(storage.get_contact(other))}\n\n{SAFETY}")
    a_line = storage.line_id_of(a_id)
    if a_line:
        line_api.push(a_line, [text(msg(b_id), MENU)])
    return [text(msg(a_id), MENU)]


def contact(line_user, msg):
    """รับ LINE ID แล้วทำขั้นที่ค้างไว้ต่อ (ส่งคำขอ / ตอบรับ)"""
    raw = msg.strip()
    link = RE_LINK.search(raw)
    value = link.group(0) if link else raw.replace(" ", "")
    if not link and not RE_ID.match(value):
        return [text("รูปแบบ LINE ID ไม่ถูกต้องครับ ลองส่งใหม่อีกครั้ง (ตัวอักษรอังกฤษ/ตัวเลข/._- 4–20 ตัว) หรือวางลิงก์เพิ่มเพื่อน")]
    a = load(line_user)
    storage.set_contact(a["user_id"], value)
    pending = line_user["state_data"]
    storage.set_state(line_user["line_user_id"], "ready")
    if pending.get("then") == "request":
        b = live.ctx().users.get(pending.get("target"))
        return _send_request(a, b) if b else [text("บันทึก LINE ID แล้วครับ", MENU)]
    if pending.get("then") == "accept":
        req = storage.get_intro(pending.get("req"))
        return _finalize(req) if req and req["status"] == "pending" else [text("บันทึก LINE ID แล้วครับ", MENU)]
    return [text("บันทึก LINE ID แล้วครับ", MENU)]
