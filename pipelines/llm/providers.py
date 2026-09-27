"""Hybrid LLM: เลือก Local (Ollama) หรือ API (PSU AI) ต่องาน + fallback อัตโนมัติ

ชื่อโมเดล:  "api:qwen/qwen3.6-flash" = API / อย่างอื่น = Ollama ในเครื่อง
นโยบายเริ่มต้น (แก้ได้ใน .env):
  งานที่อ่านข้อความส่วนตัวดิบ (extract_*)      -> Local เท่านั้น (ข้อมูลไม่ออกนอกเครื่อง)
  งานเขียนคำตอบยาว (rag_answer, explain_match)  -> API ก่อน ถ้าล้ม -> Local
"""
from . import api_client, ollama_client

PREFIX = "api:"


def is_api(model: str) -> bool:
    return model.startswith(PREFIX)


def chat(model, messages, gen, fmt=None, fallback=None):
    """เรียกโมเดลตามชื่อ; ถ้าเป็น API แล้วล้มเหลวและมี fallback (โมเดล Local) -> ใช้ fallback แทน"""
    if is_api(model):
        try:
            return api_client.chat(model[len(PREFIX):], messages, gen, fmt)
        except Exception as e:
            if not fallback:
                raise
            res = ollama_client.chat(fallback, messages, gen, fmt)
            res.metrics = {**res.metrics, "provider": "local(fallback)", "fallback_reason": str(e)[:120]}
            return res
    res = ollama_client.chat(model, messages, gen, fmt)
    res.metrics.setdefault("provider", "local")
    return res
