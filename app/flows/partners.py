"""ประวัติคู่: ตอนนี้ผู้ใช้คุยกับใคร / รอใครตอบ / ระบบแนะนำใครไปแล้ว

สรุปจาก storage.interactions ต่อ "คนอีกฝ่าย" 1 แถว (เหตุการณ์ล่าสุดชนะ):
  intros ที่ยินยอมแล้ว = คุยกันอยู่ · pending = รอตอบ · declined = จบแล้ว
  events: matched (กดสนใจผู้ใช้จำลอง) · unmatch / pass = จบแล้ว
  suggestions = ระบบแนะนำให้ (ยังไม่ได้ตัดสินใจ)
ใช้ทั้งตอบผู้ใช้ ("ตอนนี้คุยกับใครอยู่") และหาเป้าหมายของ "เลิกคุยกับคนนี้" เมื่อไม่ได้กดจากการ์ด
"""
import time

from .. import live, storage
from ..flex import MENU, text
from .common import load

LABEL = {
    "talking": "💬 แลก LINE ID แล้ว",
    "waiting_you": "💌 อีกฝ่ายส่งคำขอมา รอคุณตอบ",
    "waiting_them": "⏳ ส่งคำขอแล้ว รออีกฝ่ายตอบ",
    "interested": "⭐ คุณกดสนใจ (ผู้ใช้จำลอง)",
    "suggested": "🎯 ระบบแนะนำให้ ยังไม่ได้ตัดสินใจ",
    "declined": "🙏 ไม่ได้ไปต่อ",
    "unmatched": "👋 เลิกคุยแล้ว",
    "passed": "⏭️ ขอผ่านแล้ว",
}
# ความสำคัญเมื่อหา "คนที่คุยอยู่ตอนนี้": คุยกันจริงก่อน แล้วค่อยรอตอบ / สนใจ / แนะนำ
TALKING = ("talking", "waiting_you", "waiting_them", "interested")
ACTIVE = TALKING + ("suggested",)
MAX_SHOW = 8


def history(user_id) -> list:
    """[{user_id, status, ts}] คนละ 1 แถว ใหม่สุดก่อน (ข้ามคนที่ลบบัญชีไปแล้ว)"""
    raw = storage.interactions(user_id)
    latest = {}

    def put(other, status, ts):
        if other and other != user_id and (other not in latest or (ts or 0) >= latest[other]["ts"]):
            latest[other] = {"user_id": other, "status": status, "ts": ts or 0}

    for s in raw["suggestions"]:
        put(s["candidate_id"], "suggested", s["ts"])
    with_intro = set()
    for r in raw["intros"]:
        mine = r["from_user"] == user_id
        other = r["to_user"] if mine else r["from_user"]
        with_intro.add(other)
        if r["status"] == "accepted":
            put(other, "talking", r["decided_at"])
        elif r["status"] == "pending":
            put(other, "waiting_them" if mine else "waiting_you", r["created_at"])
        else:
            put(other, "declined", r["decided_at"])
    for e in raw["events"]:
        if e["type"] == "matched" and e["about_user"] not in with_intro:   # matched ของ intro ที่ยินยอมแล้ว = ซ้ำกับ talking
            put(e["about_user"], "interested", e["ts"])
        elif e["type"] == "unmatch":
            put(e["about_user"], "unmatched", e["ts"])
        elif e["type"] == "pass" and latest.get(e["about_user"], {}).get("status") not in ("declined",):
            put(e["about_user"], "passed", e["ts"])
    users = live.ctx().users
    return sorted((x for x in latest.values() if x["user_id"] in users), key=lambda x: -x["ts"])


def current(user_id, include_suggested=False):
    """คนที่คุยอยู่ตอนนี้ (ล่าสุดในกลุ่มที่สำคัญสุด) หรือ None"""
    rows = history(user_id)
    for group in (("talking",), ("waiting_you", "waiting_them"), ("interested",)) + ((("suggested",),) if include_suggested else ()):
        hit = [x for x in rows if x["status"] in group]
        if hit:
            return hit[0]
    return None


# "อยู่ในช่วงคุยกัน" เท่านั้น: แลก LINE ID แล้ว หรือกดสนใจผู้ใช้จำลอง (จำลองการยินยอม)
# รอตอบ / ระบบแนะนำ / เลิกคุยแล้ว = ยังไม่ได้คุย -> คำปรึกษาตอบแบบทั่วไป
IN_CONVERSATION = ("talking", "interested")


def talking_to(user_id):
    """ข้อมูลคนที่ผู้ใช้กำลังคุยด้วย สำหรับปรับคำปรึกษา หรือ None ถ้าไม่ได้อยู่ในช่วงคุยกัน

    ส่งเฉพาะนิสัยและงานอดิเรก = ข้อมูลที่การ์ดแนะนำแสดงให้ผู้ใช้เห็นอยู่แล้ว
    ไม่ส่งรูปลักษณ์ ศาสนา อาหาร ค่านิยม การถูกรายงาน หรือสิ่งที่อีกฝ่ายคุยกับบอท
    """
    now = current(user_id)
    if not now or now["status"] not in IN_CONVERSATION:
        return None
    u = live.ctx().users.get(now["user_id"]) or {}
    from pipelines.common import taxonomy
    lab = taxonomy.labels()
    p = u.get("persona", {})
    facts = [lab[x["id"]] for x in p.get("traits", [])[:3] if x.get("id") in lab]
    facts += [lab[x["id"]] for x in p.get("hobbies", [])[:4] if x.get("id") in lab]
    if not facts:
        return None
    return {"user_id": now["user_id"], "name": u.get("display_name") or "คนที่คุยอยู่", "facts": facts}


def name_of(user_id):
    u = live.ctx().users.get(user_id) or {}
    d = u.get("demographic", {})
    faculty = f" · คณะ{d['faculty']}" if d.get("faculty") else ""
    return f"{u.get('display_name') or 'ผู้ใช้'}{faculty}"


def _ago(ts):
    s = max(0, time.time() - ts)
    if s < 3600:
        return "เมื่อสักครู่"
    if s < 86400:
        return f"{int(s // 3600)} ชม.ก่อน"
    return f"{int(s // 86400)} วันก่อน"


def show(line_user):
    uid = load(line_user)["user_id"]
    rows = history(uid)
    if not rows:
        return [text("ยังไม่มีประวัติการคุยกับใครเลยครับ ลองให้ผมหาคู่ให้ก่อนไหมครับ 🙂", MENU)]
    now = current(uid)
    lines = [f"💞 ตอนนี้คุณคุยอยู่กับ: {name_of(now['user_id'])}\n({LABEL[now['status']]} · {_ago(now['ts'])})"
             if now else "ตอนนี้ยังไม่ได้เริ่มคุยกับใครครับ"]
    lines.append("\n📜 ประวัติล่าสุด")
    lines += [f"• {name_of(x['user_id'])} — {LABEL[x['status']]} ({_ago(x['ts'])})" for x in rows[:MAX_SHOW]]
    if len(rows) > MAX_SHOW:
        lines.append(f"…และอีก {len(rows) - MAX_SHOW} คน")
    return [text("\n".join(lines), MENU)]
