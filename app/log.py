"""log ของ bot ให้เห็นใน terminal ที่รัน uvicorn

รูปแบบ:  18:42:01 │ L0002 น้องมิ้น │ 💬 chat      │ "ชอบทำอาหาร..." → จำได้: hobby:cooking │ 3.2s
ตั้งค่าใน app/.env:
  LOG_LEVEL=INFO|DEBUG        (DEBUG = แสดงรายละเอียดทุกขั้น)
  LOG_TEXT=1|0                (0 = ไม่แสดงข้อความที่ผู้ใช้พิมพ์ ปกป้องความเป็นส่วนตัวเวลามีคนอื่นดูจอ)
"""
import contextvars
import logging
import os
import sys

LOG_TEXT = os.getenv("LOG_TEXT", "1") != "0"
logger = logging.getLogger("dealing")
ICON = {"follow": "➕", "unfollow": "🚫", "postback": "👆", "onboarding": "📝", "chat": "💬", "find_match": "💞",
        "ask_advice": "📚", "unmatch": "💔", "unmatch_reason": "💔", "contact": "🔗", "show_profile": "📋",
        "delete_me": "🗑️", "error": "❌", "push": "📨"}


_notes = contextvars.ContextVar("notes", default=None)


def start():
    _notes.set([])


def note(text):
    """flow เรียกเพื่อบอกว่าทำอะไรไป (รวมไว้ในบรรทัด log เดียวของ event)"""
    n = _notes.get()
    if n is not None:
        n.append(str(text))


def notes() -> str:
    return " · ".join(_notes.get() or [])


def setup():
    if logger.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s │ %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(h)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False


def who(line_user) -> str:
    if not line_user:
        return "-"
    return f"{line_user.get('user_id', '?')} {(line_user.get('display_name') or '')[:12]}".strip()


def clip(text, n=50) -> str:
    if not LOG_TEXT:
        return "(ซ่อนข้อความ)"
    t = " ".join(str(text).split())
    return f'"{t[:n]}…"' if len(t) > n else f'"{t}"'


def event(line_user, kind, detail="", seconds=None):
    tail = f" │ {seconds:.1f}s" if seconds is not None else ""
    logger.info(f"{who(line_user):<18} │ {ICON.get(kind, '•')} {kind:<14} │ {detail}{tail}")


def debug(line_user, msg):
    logger.debug(f"{who(line_user):<18} │   ↳ {msg}")
