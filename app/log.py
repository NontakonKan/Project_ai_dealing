"""log ของ bot ให้เห็นใน terminal ที่รัน uvicorn

รูปแบบ:  18:42:01 │ L0002 น้องมิ้น │ 💬 chat      │ "ชอบทำอาหาร..." → จำได้: hobby:cooking │ 3.2s
ตั้งค่าใน .env ที่ root:
  LOG_LEVEL=INFO|DEBUG        (DEBUG = แสดงรายละเอียดทุกขั้น)
  LOG_TEXT=1|0                (0 = ไม่แสดงข้อความที่ผู้ใช้พิมพ์ ปกป้องความเป็นส่วนตัวเวลามีคนอื่นดูจอ)
"""
import contextvars
import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

from pipelines.common import env

env.load()

LOG_TEXT = os.getenv("LOG_TEXT", "1") != "0"
LOG_DIR = os.path.abspath(os.getenv("LOG_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")))
APP_LOG_FILE = os.getenv("APP_LOG_FILE", os.path.join(LOG_DIR, "app.log"))
REPLY_LOG_FILE = os.getenv("REPLY_LOG_FILE", os.path.join(LOG_DIR, "reply.log"))

logger = logging.getLogger("dealing")
ICON = {"follow": "➕", "unfollow": "🚫", "postback": "👆", "onboarding": "📝", "chat": "💬", "find_match": "💞",
        "ask_advice": "📚", "unmatch": "💔", "unmatch_reason": "💔", "contact": "🔗", "show_profile": "📋",
        "delete_me": "🗑️", "out_of_domain": "🛡️", "error": "❌", "push": "📨"}

_notes = contextvars.ContextVar("notes", default=None)
_reply_logger = None


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
    os.makedirs(LOG_DIR, exist_ok=True)
    if not logger.handlers:
        # Console output
        h_console = logging.StreamHandler(sys.stdout)
        h_console.setFormatter(logging.Formatter("%(asctime)s │ %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(h_console)

        # File output (logs/app.log)
        try:
            h_file = RotatingFileHandler(APP_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
            h_file.setFormatter(logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            logger.addHandler(h_file)
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to setup app.log handler: {e}\n")

        logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        logger.propagate = False


def _get_reply_logger():
    global _reply_logger
    if _reply_logger is None:
        os.makedirs(LOG_DIR, exist_ok=True)
        rl = logging.getLogger("dealing.reply")
        if not rl.handlers:
            try:
                rh = RotatingFileHandler(REPLY_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
                rh.setFormatter(logging.Formatter("%(message)s"))
                rl.addHandler(rh)
                rl.setLevel(logging.INFO)
                rl.propagate = False
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to setup reply.log handler: {e}\n")
        _reply_logger = rl
    return _reply_logger


def record_reply(user, kind, user_input, notes, msgs, seconds=None, error=None):
    """บันทึกข้อมูลเวลาตอบ reply ทุกข้อความลง logs/reply.log อัตโนมัติสำหรับการ debug"""
    try:
        rl = _get_reply_logger()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uname = who(user)
        uid = (user or {}).get("line_user_id") or (user or {}).get("user_id") or "-"
        sec_str = f"{seconds:.2f}s" if seconds is not None else "-"

        reply_blocks = []
        for i, m in enumerate(msgs or [], 1):
            if m.get("type") == "flex":
                alt = m.get("altText", "")
                reply_blocks.append(f"  [Message {i} - Card Flex]: {alt}")
            else:
                txt = m.get("text", "")
                reply_blocks.append(f"  [Message {i} - Text]:\n{txt}")
        reply_str = "\n".join(reply_blocks) if reply_blocks else "  (ไม่มีข้อความตอบกลับ)"

        err_str = f"\nERROR:\n{error}\n" if error else ""

        entry = (
            f"\n{'=' * 80}\n"
            f"[{now}] KIND: {kind} │ DURATION: {sec_str}\n"
            f"USER: {uname} (ID: {uid})\n"
            f"INPUT:\n{user_input if user_input else '(ไม่มี input)'}\n"
            f"NOTES:\n{notes if notes else '-'}\n"
            f"REPLY:\n{reply_str}"
            f"{err_str}\n"
            f"{'=' * 80}"
        )
        rl.info(entry)
    except Exception as e:
        logger.warning(f"บันทึก reply log ไม่สำเร็จ: {e}")


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

