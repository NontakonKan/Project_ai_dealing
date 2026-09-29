"""Webhook server (FastAPI)

  uvicorn app.server:api --host 0.0.0.0 --port 8000
  ngrok http 8000  -> ตั้ง Webhook URL = https://<ngrok>/callback ใน LINE Developers Console
"""
import json

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from . import handlers, line_api, live, log
from .config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET

api = FastAPI(title="PSU Dealing LINE bot")


def _preload(c):
    """โหลดของหนักก่อนมีคนทัก: Dense index + embedding + cross-encoder + โมเดล Local ที่ใช้บ่อย"""
    import time
    from pipelines.dense.embedding import encode
    from pipelines.llm import ollama_client, providers
    from pipelines.llm.config import TASKS, GenConfig
    from .config import CHAT_MODEL
    t0 = time.time()
    c.dense                      # ChromaDB
    encode(["warmup"])           # bge-m3 (sentence-transformers)
    from .intent_model import _index
    _index()                     # เข้ารหัสประโยคตัวอย่างของแต่ละเจตนา (แยกเจตนาด้วยความหมาย)
    from pipelines.hybrid.reranker import _model
    _model().predict([("warmup", "warmup")], show_progress_bar=False)   # cross-encoder ของด่านความเกี่ยวข้อง (ตอบปรึกษา)
    for m in {TASKS["extract_profile"].model, CHAT_MODEL}:
        if not providers.is_api(m):
            try:
                ollama_client.chat(m, [{"role": "user", "content": "hi"}], GenConfig(num_predict=1))
            except Exception:
                pass
    log.logger.info(f"🔥 โหลดโมเดลล่วงหน้าเสร็จ ({time.time() - t0:.1f}s)")


@api.on_event("startup")
def warmup():
    log.setup()
    c = live.ctx()   # โหลด Hybrid context ล่วงหน้า (ข้อความแรกจะได้ไม่ช้า)
    _preload(c)
    n_live = sum(u.get("source") == "line" for u in c.users.values())
    log.logger.info(f"🚀 bot พร้อม │ LINE {'เชื่อมแล้ว' if LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN else 'ยังไม่ตั้งค่า (โหมดจำลอง)'}"
                    f" │ ผู้ใช้ในระบบ {len(c.users)} (จริง {n_live}, จำลอง {len(c.users) - n_live})")


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
