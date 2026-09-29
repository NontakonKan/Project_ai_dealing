"""โหลด .env ไฟล์เดียวที่ root ของโปรเจกต์เข้า os.environ โดยไม่ทับค่าที่ตั้งไว้แล้ว"""
import os

from .paths import ROOT

_loaded = False


def load():
    global _loaded
    if _loaded:
        return
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())
    _loaded = True
