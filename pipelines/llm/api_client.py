"""API LLM (OpenAI-compatible) — ใช้กับ PSU AI (https://ai.psu.blue/v1) หรือ provider อื่นที่เป็นมาตรฐานเดียวกัน

- structured output: ลอง json_schema -> json_object -> ไม่บังคับ (gateway บางตัวไม่รองรับ) แล้วจำไว้ต่อโมเดล
- หมุน API keys และพัก key ที่เจอ 429 / 5xx / timeout ก่อนสลับตัวถัดไป
- metric: wall_ms, prompt/gen tokens (จาก usage), gen_tok_s, cost_usd (ถ้าตั้งราคาไว้)
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

from ..common import env
from .ollama_client import LLMResult, OllamaError

env.load()
BASE_URL = os.getenv("API_BASE_URL", "https://ai.psu.blue/v1").rstrip("/")
TIMEOUT_S = 120
_schema_support = {}                       # model -> "json_schema" | "json_object" | "none"
RE_THINK = re.compile(r"<think>.*?</think>", re.S)


class ApiError(OllamaError):
    pass


def api_key():
    return api_keys()[0] if api_keys() else ""


def api_keys():
    """Three team keys, with the old single-key setting kept for compatibility."""
    values = [os.getenv(f"API_KEY_{i}", "").strip() for i in range(1, 4)]
    values = [value for value in values if value]
    if not values:
        values = [(os.getenv("API_KEY") or os.getenv("PSU_AI_API_KEY") or "").strip()]
    return list(dict.fromkeys(value for value in values if value))


def available() -> bool:
    return bool(api_keys())


_key_lock = threading.Lock()
_next_key = 0
_key_blocked_until = {}  # key -> monotonic deadline; never expose keys in logs


def _candidates():
    global _next_key
    keys = api_keys()
    with _key_lock:
        start = _next_key % len(keys)
        _next_key += 1
        now = time.monotonic()
        return [key for key in (keys[(start + i) % len(keys)] for i in range(len(keys)))
                if _key_blocked_until.get(key, 0) <= now]


def _block(key, seconds):
    with _key_lock:
        _key_blocked_until[key] = time.monotonic() + seconds


# ตัวคูณเครดิตรายวันของ PSU AI (หน้า API Keys, 2026-09-27): 0 = ฟรี, 1 = x1 ...
CREDIT_MULTIPLIER = {
    "PSU-LLM/psu-gemma": 0, "deepseek/deepseek-chat": 1, "openai/gpt-4o-mini": 1, "qwen/qwen3.6-plus": 1,
    "qwen/qwen3.6-flash": 1, "qwen/qwen3.6-27b": 1, "deepseek/deepseek-v4-flash-0731": 1, "qwen/qwen3.8-27b": 1,
    "z-ai/glm-5": 2, "openai/gpt-5.6-luna": 2, "qwen/qwen3.7-plus": 3,
}


def credits(model, prompt_tokens, gen_tokens):
    """เครดิตที่ใช้ = token ทั้งหมด x ตัวคูณของโมเดล (หน่วยเทียบกันเองระหว่างโมเดล)"""
    m = CREDIT_MULTIPLIER.get(model)
    return None if m is None else (prompt_tokens + gen_tokens) * m


def price(model):
    """ราคา USD ต่อ 1M token (in, out) — ตั้งใน .env: API_PRICE_<ชื่อโมเดลแบบตัวใหญ่ _> = in,out"""
    key = "API_PRICE_" + re.sub(r"[^A-Z0-9]", "_", model.upper())
    raw = os.getenv(key, os.getenv("API_PRICE_DEFAULT", ""))
    try:
        pin, pout = (float(x) for x in raw.split(","))
        return pin, pout
    except ValueError:
        return None


USER_AGENT = "psu-dealing/1.0 (+https://github.com/NontakonKan/Project_ai_dealing)"   # Cloudflare บล็อก UA ของ Python (error 1010)


def _post(payload, key):
    payload = {**payload, "stream": False}
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                                          "User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    return _parse(raw)


def _parse(raw: str) -> dict:
    """JSON ปกติ หรือ SSE (gateway บางตัวส่ง stream แม้ขอ stream=false) -> รูปแบบ chat.completion เดียวกัน"""
    if not raw.lstrip().startswith("data:"):
        return json.loads(raw)
    text, usage, finish = [], {}, None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        chunk = json.loads(line[5:])
        for ch in chunk.get("choices", []):
            text.append((ch.get("delta") or {}).get("content") or "")
            finish = ch.get("finish_reason") or finish
        usage = chunk.get("usage") or usage
    return {"choices": [{"message": {"content": "".join(text)}, "finish_reason": finish}], "usage": usage}


def _formats(model, fmt):
    if fmt is None:
        return [None]
    order = ["json_schema", "json_object", "none"]
    known = _schema_support.get(model)
    return order[order.index(known):] if known else order


def _response_format(kind, fmt):
    if kind == "json_schema" and isinstance(fmt, dict):
        return {"type": "json_schema", "json_schema": {"name": "output", "schema": fmt, "strict": False}}
    if kind == "json_object":
        return {"type": "json_object"}
    return None


def chat(model, messages, gen, fmt=None) -> LLMResult:
    if not available():
        raise ApiError("ยังไม่ได้ตั้ง API_KEY_1..3 หรือ API_KEY ใน .env")
    last = None
    for kind in _formats(model, fmt):
        payload = {"model": model, "messages": messages, "temperature": gen.temperature,
                   "max_tokens": gen.num_predict, "top_p": gen.top_p, "seed": gen.seed}
        rf = _response_format(kind, fmt) if fmt is not None else None
        if rf:
            payload["response_format"] = rf
        unsupported_format = False
        for key in _candidates():
            t0 = time.perf_counter()
            try:
                d = _post(payload, key)
                if fmt is not None:
                    _schema_support[model] = kind
                return _result(model, d, (time.perf_counter() - t0) * 1000)
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="ignore")[:300]
                if e.code == 400 and rf:           # ไม่รองรับ response_format แบบนี้ -> ลองแบบถัดไป
                    last = ApiError(f"HTTP 400 ({kind}): {body}")
                    unsupported_format = True
                    break
                if e.code in (401, 403):
                    _block(key, 3600)
                    last = ApiError(f"API key ใช้ไม่ได้ (HTTP {e.code})")
                    continue
                if e.code == 404:
                    raise ApiError(f"ไม่พบโมเดล {model}") from e
                last = ApiError(f"HTTP {e.code}: {body}")
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    try:
                        seconds = min(max(float(retry_after), 1), 86400)
                    except (TypeError, ValueError):
                        seconds = 60
                    _block(key, seconds)
                elif e.code >= 500:
                    _block(key, 15)
                else:
                    raise last
            except (urllib.error.URLError, TimeoutError) as e:
                last = ApiError(f"เชื่อมต่อ API ไม่ได้: {e}")
                _block(key, 15)
        if unsupported_format:
            continue
        break
    raise last or ApiError("API ล้มเหลว")


def _result(model, d, wall_ms) -> LLMResult:
    msg = d["choices"][0]["message"]
    text = RE_THINK.sub("", msg.get("content") or "").strip()
    u = d.get("usage") or {}
    pin, pout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    p = price(model)
    metrics = {"provider": "api", "wall_ms": round(wall_ms, 1), "load_ms": 0.0, "prompt_tokens": pin,
               "prompt_ms": None, "gen_tokens": pout, "gen_ms": None,
               "prompt_tok_s": None, "gen_tok_s": round(pout / (wall_ms / 1000), 1) if wall_ms and pout else None,
               "truncated": d["choices"][0].get("finish_reason") == "length",
               "cost_usd": round((pin * p[0] + pout * p[1]) / 1e6, 6) if p else None,
               "credits": credits(model, pin, pout)}
    return LLMResult(text, model, metrics)


def list_models() -> list:
    req = urllib.request.Request(f"{BASE_URL}/models", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as r:
        return [m["id"] for m in json.loads(r.read())["data"]]
