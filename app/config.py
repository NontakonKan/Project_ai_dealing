"""ค่าตั้งของ service — อ่านจาก environment / .env ที่ root (ไม่ขึ้น git)

LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN ว่าง = โหมดจำลอง (ไม่ส่งจริง ใช้กับ app.simulate)
"""
import os
from pathlib import Path

from pipelines.common import env
from pipelines.common.paths import DATA

env.load()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
DB_PATH = Path(os.getenv("APP_DB", DATA / "app" / "psu_dealing.db"))

# ผู้ใช้จำลองที่อยู่ใน pool ร่วมกับผู้ใช้จริง: "all" = ทั้ง 300 คน / หรือรายการ id คั่นด้วย ,
MOCK_USERS = os.getenv("MOCK_USERS", "all").strip()

CHAT_MODEL = os.getenv("CHAT_MODEL", "scb10x/llama3.1-typhoon2-8b-instruct")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "scb10x/llama3.2-typhoon2-3b-instruct")
HISTORY_TURNS = 6            # ข้อความล่าสุดที่ส่งให้ LLM ตอนคุยเล่น
MAX_HOBBIES, MAX_TRAITS = 8, 6
DECAY_HALF_LIFE_DAYS, MIN_CONFIDENCE = 60, 0.3
