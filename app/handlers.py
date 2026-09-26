"""รับ LINE event -> เลือก flow -> ส่งข้อความกลับ (มี error handling ทุก event)

event ที่รองรับ: follow, unfollow, message(text), postback
"""
import sys
import time
import traceback
from urllib.parse import parse_qs

from . import intent, line_api, storage
from .flex import MENU, text
from .flows import account, advice, chat, intro, match, onboarding, unmatch

ERROR_TEXT = "ขอโทษครับ ตอนนี้ระบบขัดข้องชั่วคราว 🙏 ลองพิมพ์ใหม่อีกครั้งได้ไหมครับ"


def _user(line_user_id):
    return storage.get_line_user(line_user_id) or storage.create_line_user(line_user_id, line_api.get_display_name(line_user_id))


def dispatch(event) -> list:
    etype = event.get("type")
    lid = event.get("source", {}).get("userId")
    if not lid:
        return []
    if etype == "follow":
        return onboarding.follow(_user(lid))
    u = _user(lid)
    if etype == "unfollow":
        return onboarding.unfollow(u)
    if etype == "postback":
        q = {k: v[0] for k, v in parse_qs(event["postback"]["data"]).items()}
        act, target = q.get("action"), q.get("target")
        if act == "consent":
            return onboarding.consent(u, q.get("v") == "yes")
        if act == "sensitive":
            return chat.sensitive_consent(u, q.get("v") == "yes")
        if act == "intro":
            return intro.request(u, target)
        if act in ("accept", "decline"):
            return intro.decide(u, q.get("req"), act == "accept")
        if act == "pass":
            return match.pass_(u, target)
        if act == "unmatch":
            return unmatch.ask_reason(u, target)
        return []
    if etype == "message" and event["message"].get("type") == "text":
        msg = event["message"]["text"]
        if u["state"] == "new":
            return onboarding.follow(u)
        if msg.strip() in ("ยินยอม", "ยินยอมให้หาคู่") and u["state"] != "onboard_consent":
            return onboarding.consent(u, True)
        kind = intent.classify(msg, u["state"])
        storage.add_message(u["user_id"], "user", msg, kind)
        out = {"onboarding": lambda: onboarding.answer(u, msg), "unmatch_reason": lambda: unmatch.reason(u, msg),
               "contact": lambda: intro.contact(u, msg),
               "delete_me": lambda: account.delete(u), "show_profile": lambda: account.show(u),
               "find_match": lambda: match.find(u), "unmatch": lambda: unmatch.ask_reason(u),
               "ask_advice": lambda: advice.handle(u, msg), "chat": lambda: chat.handle(u, msg)}[kind]()
        for m in out:
            if m["type"] == "text" and kind != "delete_me":
                storage.add_message(u["user_id"], "bot", m["text"], kind)
        return out
    if etype == "message":
        return [text("ตอนนี้ผมอ่านได้แค่ข้อความนะครับ 🙂", MENU)]
    return []


def handle(event):
    """เรียกจาก webhook (background) — ห้ามให้ exception หลุด; ตอบภายในเวลาของ replyToken ถ้าทำได้ ไม่งั้น push"""
    t0 = time.time()
    lid = event.get("source", {}).get("userId")
    try:
        msgs = dispatch(event)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        msgs = [text(ERROR_TEXT, MENU)]
    if not msgs:
        return msgs
    if event.get("replyToken") and time.time() - t0 < 50:
        line_api.reply(event["replyToken"], msgs, to=lid)
    elif lid:
        line_api.push(lid, msgs)
    return msgs
