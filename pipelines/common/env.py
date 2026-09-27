"""โหลดค่าจาก .env ที่ root ของโปรเจกต์ และ app/.env (ไม่ขึ้น git) เข้า os.environ — ไม่ทับค่าที่ตั้งไว้แล้ว"""
import os

from .paths import ROOT

_loaded = False


def load():
    global _loaded
    if _loaded:
        return
    for path in (ROOT / ".env", ROOT / "app" / ".env"):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    if v.strip():
                        os.environ.setdefault(k.strip(), v.strip())
    _loaded = True
