"""ค่าตั้งของ service — อ่านจาก environment / app/.env (ไม่ขึ้น git)

LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN ว่าง = โหมดจำลอง (ไม่ส่งจริง ใช้กับ app.simulate)
"""
import os
from pathlib import Path

from pipelines.common.paths import DATA

ENV_FILE = Path(__file__).with_name(".env")
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
DB_PATH = Path(os.getenv("APP_DB", DATA / "app" / "psu_dealing.db"))

CHAT_MODEL = os.getenv("CHAT_MODEL", "scb10x/llama3.1-typhoon2-8b-instruct")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "scb10x/llama3.2-typhoon2-3b-instruct")
HISTORY_TURNS = 6            # ข้อความล่าสุดที่ส่งให้ LLM ตอนคุยเล่น
MAX_HOBBIES, MAX_TRAITS = 8, 6
DECAY_HALF_LIFE_DAYS, MIN_CONFIDENCE = 60, 0.3
