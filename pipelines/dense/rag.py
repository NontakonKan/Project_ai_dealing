"""Select retrieved context and ask an OpenAI-compatible local or hosted LLM."""
import json
import os
import time
from urllib.request import Request, urlopen

from .matching import load_matching_data, rank


def context_for_match(user_id, index, top_k=5, threshold=0.0, penalty_weight=0.15, knowledge_k=3):
    users, events = load_matching_data()
    matches = rank(user_id, index, users, events, top_k, threshold, penalty_weight)
    if not matches:
        return {"user_id": user_id, "matches": [], "knowledge": []}
    primary = matches[0]["user_id"]
    a = users[user_id]["summaries"]
    b = users[primary]["summaries"]
    query = f"{a.get('preference_text', '')} {a.get('avoid_text', '')} {b.get('persona_text', '')}"
    knowledge = index.search("knowledge", query, top_k=knowledge_k)
    compact = []
    for item in matches:
        uid = item["user_id"]
        compact.append({**item, "persona_text": users[uid]["summaries"]["persona_text"]})
    return {"user_id": user_id, "query_persona": a.get("persona_text", ""),
            "query_preference": a.get("preference_text", ""), "matches": compact,
            "knowledge": knowledge}


def answer_with_llm(context, *, endpoint=None, model=None, api_key=None, timeout=60):
    endpoint = endpoint or os.environ.get("DENSE_LLM_ENDPOINT")
    model = model or os.environ.get("DENSE_LLM_MODEL")
    api_key = api_key or os.environ.get("DENSE_LLM_API_KEY")
    if not endpoint or not model:
        raise ValueError("Set DENSE_LLM_ENDPOINT and DENSE_LLM_MODEL for LLM answers")
    endpoint = endpoint.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    payload = {"model": model, "temperature": 0.2, "max_tokens": 500,
               "messages": [
                   {"role": "system", "content": "ตอบเป็นภาษาไทยโดยใช้เฉพาะบริบทที่ให้ ระบุ user_id และ chunk_id ที่อ้างอิง อธิบายว่าเป็นคำแนะนำเบื้องต้นและอย่าสร้างข้อเท็จจริงเพิ่ม"},
                   {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)
    started = time.perf_counter()
    with urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    return {"answer": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}), "latency_seconds": round(time.perf_counter() - started, 3),
            "model": model}
