"""HTTP client ของ Ollama (stdlib) + ดึง metric เวลา/จำนวน token จาก response"""
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .config import OLLAMA_URL, RETRIES, TIMEOUT_S


class OllamaError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    model: str
    metrics: dict = field(default_factory=dict)


def _post(path, payload, timeout=TIMEOUT_S):
    req = urllib.request.Request(f"{OLLAMA_URL}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(path):
    with urllib.request.urlopen(f"{OLLAMA_URL}{path}", timeout=10) as r:
        return json.loads(r.read())


def metrics_from(d: dict, wall_ms: float) -> dict:
    ns = lambda k: d.get(k, 0) / 1e6
    gen_ms, prompt_ms = ns("eval_duration"), ns("prompt_eval_duration")
    return {
        "wall_ms": round(wall_ms, 1),
        "load_ms": round(ns("load_duration"), 1),
        "prompt_tokens": d.get("prompt_eval_count", 0),
        "prompt_ms": round(prompt_ms, 1),
        "gen_tokens": d.get("eval_count", 0),
        "gen_ms": round(gen_ms, 1),
        "prompt_tok_s": round(d.get("prompt_eval_count", 0) / (prompt_ms / 1000), 1) if prompt_ms else None,
        "gen_tok_s": round(d.get("eval_count", 0) / (gen_ms / 1000), 1) if gen_ms else None,
        "truncated": d.get("done_reason") == "length",
    }


def chat(model, messages, gen, fmt=None) -> LLMResult:
    payload = {"model": model, "messages": messages, "stream": False, "options": gen.options(),
               "keep_alive": gen.keep_alive}
    if fmt is not None:
        payload["format"] = fmt
    last = None
    for attempt in range(RETRIES + 1):
        t0 = time.perf_counter()
        try:
            d = _post("/api/chat", payload)
            return LLMResult(d["message"]["content"], model, metrics_from(d, (time.perf_counter() - t0) * 1000))
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            if e.code == 404:
                raise OllamaError(f"ไม่พบโมเดล {model} — รัน `ollama pull {model}`") from e
            last = OllamaError(f"HTTP {e.code}: {body[:200]}")
        except (urllib.error.URLError, TimeoutError) as e:
            last = OllamaError(f"เชื่อมต่อ Ollama ไม่ได้ ({OLLAMA_URL}): {e}")
        time.sleep(1.5 * (attempt + 1))
    raise last


def list_models() -> list:
    return [{"name": m["name"], "size_gb": round(m["size"] / 1e9, 2),
             "params": m.get("details", {}).get("parameter_size"),
             "quant": m.get("details", {}).get("quantization_level")} for m in _get("/api/tags")["models"]]


def loaded() -> list:
    return [{"name": m["name"], "size_gb": round(m["size"] / 1e9, 2), "vram_gb": round(m.get("size_vram", 0) / 1e9, 2),
             "context_length": m.get("context_length")} for m in _get("/api/ps")["models"]]


def unload(model):
    _post("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)


def embed(model, texts: list) -> list:
    """embedding ผ่าน Ollama (/api/embed) คืน list ของ vector"""
    try:
        return _post("/api/embed", {"model": model, "input": texts})["embeddings"]
    except urllib.error.URLError as e:
        raise OllamaError(f"embed ไม่สำเร็จ ({model}): {e}") from e
