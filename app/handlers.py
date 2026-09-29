"""รับ LINE event -> เลือก flow -> ส่งข้อความกลับ (มี error handling ทุก event)

event ที่รองรับ: follow, unfollow, message(text), postback
"""
import sys
import time
import traceback
import threading
from urllib.parse import parse_qs

from . import conversation, intent, line_api, log, storage
from .flex import MENU, delete_confirmation_card, postback_quick, text
from .flows import account, advice, chat, intro, match, onboarding, unmatch

ERROR_TEXT = "ขอโทษครับ ตอนนี้ระบบขัดข้องชั่วคราว 🙏 ลองพิมพ์ใหม่อีกครั้งได้ไหมครับ"


def _user(line_user_id):
    return storage.get_line_user(line_user_id) or storage.create_line_user(line_user_id, line_api.get_display_name(line_user_id))


def _summary(msgs):
    out = []
    for m in msgs:
        out.append(f"[การ์ด] {m.get('altText', '')[:40]}" if m["type"] == "flex" else f"ตอบ {log.clip(m.get('text', ''), 35)}")
    return " / ".join(out)


_trace = {}


# Bounded lock pool: serialize one user's turns within a server process.
# RLock also permits handle() to cover delivery while dispatch() protects direct callers.
_CONVERSATION_LOCKS = [threading.RLock() for _ in range(64)]


def _conversation_lock(event):
    uid = event.get("source", {}).get("userId", "")
    return _CONVERSATION_LOCKS[hash(uid) % len(_CONVERSATION_LOCKS)]


def dispatch(event) -> list:
    with _conversation_lock(event):
        return _dispatch(event)


def _dispatch(event) -> list:
    etype = event.get("type")
    lid = event.get("source", {}).get("userId")
    if not lid:
        return []
    if etype == "follow":
        u = _user(lid)
        _trace.update(user=u, kind="follow", input="เพิ่มเพื่อน OA", raw_input="เพิ่มเพื่อน OA")
        return onboarding.follow(u)
    u = _user(lid)
    _trace.update(user=u, kind=etype, input="", raw_input="")
    if etype == "unfollow":
        return onboarding.unfollow(u)
    if etype == "postback":
        q = {k: v[0] for k, v in parse_qs(event["postback"]["data"]).items()}
        act, target = q.get("action"), q.get("target")
        _trace.update(kind="postback", input=f"กดปุ่ม {act}" + (f" → {target}" if target else ""),
                      raw_input=f"action={act}" + (f"&target={target}" if target else ""))
        if act == "consent":
            return onboarding.consent(u, q.get("v") == "yes")
        if act == "sensitive":
            return chat.sensitive_consent(u, q.get("v") == "yes")
        if act == "sensitive_values":
            return chat.sensitive_values_consent(u, q.get("v") == "yes")
        if act == "intro":
            return intro.request(u, target)
        if act in ("accept", "decline"):
            return intro.decide(u, q.get("req"), act == "accept")
        if act == "delete":
            if q.get("v") == "yes":
                return account.delete(u)
            return [text("ยกเลิกแล้วครับ ข้อมูลของคุณยังอยู่ครบ 🙂", MENU)]
        if act == "delete_prompt":
            return [delete_confirmation_card()]
        if act == "delete_confirm":
            return account.delete(u)
        if act == "delete_cancel":
            return [text("ยกเลิกการลบข้อมูลแล้วครับ", MENU)]
        if act == "pass":
            return match.pass_(u, target)
        if act == "unmatch":
            return unmatch.ask_reason(u, target)
        return []
    if etype == "message" and event["message"].get("type") == "text":
        msg = event["message"]["text"]
        if u["state"] == "new":
            return onboarding.follow(u)
        if msg.strip() == "ถามบอต" and u["state"] == "ready":
            return [text("อยากถามหรือปรึกษาเรื่องอะไรครับ พิมพ์คำถามมาได้เลย เช่น วิธีเริ่มคุยกับคนที่ชอบ หรือการตั้งขอบเขตในความสัมพันธ์", MENU)]
        if msg.strip() in ("ยินยอม", "ยินยอมให้หาคู่") and u["state"] != "onboard_consent":
            return onboarding.consent(u, True)
        # Anchor history to the inserted row, never remove an assumed last row.
        message_id = storage.add_message(u["user_id"], "user", msg)
        history = storage.advice_history(u["user_id"], message_id)
        kind = intent.classify(msg, u["state"], history=history)
        if intent.LAST:
            log.note(f"เจตนา={intent.LAST['raw']} ตัดสินด้วย {intent.LAST['by']} {intent.LAST['top'][:2]}")
        with storage.db() as con:
            con.execute("UPDATE messages SET intent=? WHERE id=?", (kind, message_id))
        memories = []
        if kind in {"ask_advice", "recall_memory"}:
            memories = conversation.prepare(u["user_id"], msg, message_id, history)
            if memories and intent.is_followup(msg) and kind != "recall_memory":
                import json
                # Explicitly labelled user context, never assistant-generated evidence.
                memory_context = {"role": "user", "text":
                    "บันทึกความจำส่วนตัว (ไม่ใช่หลักฐานความรู้; ข้อมูลใหม่แทนข้อมูลเก่าที่ขัดกัน): "
                    + json.dumps(memories, ensure_ascii=False)}
                history = [memory_context] + history
        if kind == "recall_memory":
            if not memories:
                out = [text("ยังไม่พบบันทึกที่เกี่ยวข้องครับ ช่วยระบุหัวข้อที่เคยคุยอีกนิดได้ไหมครับ", MENU)]
            else:
                try:
                    from pipelines.llm import tasks
                    out = [text(tasks.recall_answer(msg, memories), MENU)]
                except Exception:
                    out = [text("ตอนนี้อ่านความจำไม่สำเร็จครับ ลองถามอีกครั้งได้ไหมครับ", MENU)]
            for reply in out:
                storage.add_message(u["user_id"], "bot", reply["text"], kind)
            return out
        _trace.update(kind=kind, input=log.clip(msg) if kind != "contact" else "(ส่ง LINE ID — ไม่แสดงใน log)",
                      raw_input=msg if kind != "contact" else "(LINE ID)")
        flows = {
            "onboarding": lambda: onboarding.answer(u, msg),
            "unmatch_reason": lambda: unmatch.reason(u, msg),
            "contact": lambda: intro.contact(u, msg),
            "delete_me": lambda: account.confirm_delete(u),
            "show_profile": lambda: account.show(u),
            "find_match": lambda: match.find(u),
            "unmatch": lambda: unmatch.ask_reason(u),
            "ask_advice": lambda: advice.handle(u, msg, history=history),
            "out_of_domain": lambda: [text("เรื่องนี้ผมไม่มีข้อมูลและไม่สามารถตอบได้ครับ 😅 ผมเป็นผู้ช่วยหาคู่และให้คำปรึกษาเรื่องความสัมพันธ์สำหรับนักศึกษา ม.อ. เท่านั้นครับ\n\nสามารถเล่าสเปกคนที่ชอบ ปรึกษาปัญหาความรัก หรือพิมพ์ 'หาคู่ให้หน่อย' ได้เลยนะครับ!", MENU)],
            "chat": lambda: chat.handle(u, msg),
        }
        out = flows.get(kind, lambda: chat.handle(u, msg))()
        for m in out:
            if m["type"] == "text" and kind != "delete_me":
                storage.add_message(u["user_id"], "bot", m["text"], kind)
        return out
    if etype == "message":
        return [text("ตอนนี้ผมอ่านได้แค่ข้อความนะครับ 🙂", MENU)]
    return []


def handle(event):
    with _conversation_lock(event):
        return _handle(event)


def _handle(event):
    """เรียกจาก webhook (background) — ห้ามให้ exception หลุด; ตอบภายในเวลาของ replyToken ถ้าทำได้ ไม่งั้น push"""
    t0 = time.time()
    lid = event.get("source", {}).get("userId")
    if event.get("source", {}).get("type") == "user" and event.get("type") in ("message", "postback"):
        line_api.show_loading(lid)      # จุดเด้งระหว่างค้น + LLM (บางคำถามใช้ 10-30 วินาที)
    _trace.clear()
    log.start()
    err_detail = None
    try:
        msgs = dispatch(event)
        kind = _trace.get("kind", event.get("type"))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        err_detail = traceback.format_exc()
        msgs, kind = [text(ERROR_TEXT, MENU)], "error"
        log.note(f"{type(e).__name__}: {e}")
    if _trace.get("user") or kind == "error":
        parts = [p for p in (_trace.get("input"), log.notes(), _summary(msgs)) if p]
        log.event(_trace.get("user"), kind, " → ".join(parts), time.time() - t0)
        log.record_reply(
            user=_trace.get("user"),
            kind=kind,
            user_input=_trace.get("raw_input", _trace.get("input", "")),
            notes=log.notes(),
            msgs=msgs,
            seconds=time.time() - t0,
            error=err_detail,
        )
    if not msgs:
        return msgs
    if event.get("replyToken") and time.time() - t0 < 50:
        line_api.reply(event["replyToken"], msgs, to=lid)
    elif lid:
        line_api.push(lid, msgs)
    return msgs
