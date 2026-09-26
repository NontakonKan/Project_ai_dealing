"""LINE Messaging API: ตรวจลายเซ็น + reply/push/get_profile (stdlib ไม่ต้องใช้ SDK)

ไม่มี access token -> โหมดจำลอง: เก็บข้อความไว้ใน outbox แทนการส่งจริง (app.simulate อ่านจากตรงนี้)
"""
import base64
import hashlib
import hmac
import json
import urllib.request

from .config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET

API = "https://api.line.me/v2/bot"
outbox = []   # โหมดจำลอง


def verify_signature(body: bytes, signature: str, secret: str = None) -> bool:
    secret = LINE_CHANNEL_SECRET if secret is None else secret
    if not secret:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature or "")


def _post(path, payload):
    req = urllib.request.Request(f"{API}{path}", data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def reply(reply_token, messages, to=None):
    """reply token ใช้ได้ครั้งเดียวและหมดอายุ ~1 นาที -> ถ้าล้มเหลวและรู้ผู้รับ ใช้ push แทน"""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        outbox.append({"to": to, "messages": messages})
        return
    try:
        _post("/message/reply", {"replyToken": reply_token, "messages": messages[:5]})
    except Exception:
        if to:
            push(to, messages)


def push(to, messages):
    from . import log, storage
    u = storage.get_line_user(to)
    log.note(f"📨 push ถึง {u['user_id'] if u else '?'} ({len(messages)} ข้อความ)")
    if not LINE_CHANNEL_ACCESS_TOKEN:
        outbox.append({"to": to, "messages": messages})
        return
    _post("/message/push", {"to": to, "messages": messages[:5]})


def get_display_name(line_user_id):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return "ผู้ทดสอบ"
    req = urllib.request.Request(f"{API}/profile/{line_user_id}", headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("displayName", "")
    except Exception:
        return ""
