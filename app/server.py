"""Webhook server (FastAPI)

  uvicorn app.server:api --host 0.0.0.0 --port 8000
  ngrok http 8000  -> ตั้ง Webhook URL = https://<ngrok>/callback ใน LINE Developers Console
"""
import json

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from . import handlers, line_api, live
from .config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET

api = FastAPI(title="PSU Dealing LINE bot")


@api.on_event("startup")
def warmup():
    live.ctx()   # โหลด Hybrid context ล่วงหน้า (ข้อความแรกจะได้ไม่ช้า)


@api.get("/health")
def health():
    c = live.ctx()
    return {"ok": True, "line_configured": bool(LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN),
            "users": len(c.users), "live_users": sum(u.get("source") == "line" for u in c.users.values())}


@api.post("/callback")
async def callback(request: Request, background: BackgroundTasks, x_line_signature: str = Header(default="")):
    body = await request.body()
    if not line_api.verify_signature(body, x_line_signature):
        raise HTTPException(status_code=401, detail="invalid signature")
    for event in json.loads(body).get("events", []):
        background.add_task(handlers.handle, event)   # ตอบ 200 ทันที แล้วประมวลผลเบื้องหลัง
    return {"ok": True}
