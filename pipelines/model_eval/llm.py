"""LLM 5 Local + 5 API: ตอบคำถามจาก context ชุดเดียวกัน (data.frozen_contexts) ด้วย prompt และค่าเดียวกับบอท

เรียกโมเดลตรง ไม่มี fallback (ถ้า API ล่มแล้วสลับเป็น Local ผลจะไม่ใช่ของโมเดลนั้น) — เรียกไม่สำเร็จนับเป็น error
ตัวชี้วัด:
  answered     คำถามตอบได้ -> ตอบ (ไม่ใช่ "ไม่มีข้อมูลเพียงพอ")
  refused      คำถามนอกคลัง -> ตอบว่าไม่มีข้อมูล (context เป็น 3 อันดับแรกที่ไม่ตรงคำถาม)
  grounded     สัดส่วนท่อนคำตอบที่มีหลักฐานในเอกสาร (ตัวตรวจเดียวกับด่านหลังของบอท: verify_answer)
  keyword      คำตอบมีคำคาดหวัง >= ครึ่งหนึ่ง
  cited        ใส่เลขอ้างอิง [n] ที่มีอยู่จริง
"""
import json
import statistics
import time

from ..hybrid.gate import _CITE, _SENT, _clauses, verify_answer
from ..llm import api_client, ollama_client, parsing, prompts
from ..llm.config import TASKS
from .data import OUT, frozen_contexts, questions, relevant

LOCAL = {
    "Typhoon2 8B": "scb10x/llama3.1-typhoon2-8b-instruct",
    "Qwen2.5 7B": "qwen2.5:latest",
    "Gemma3 12B": "gemma3:12b",
    "Gemma3 4B": "gemma3:4b",
    "Typhoon2 3B": "scb10x/llama3.2-typhoon2-3b-instruct",
}
API = {
    "psu-gemma (ฟรี)": "PSU-LLM/psu-gemma",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash-0731",
    "qwen3.6-flash": "qwen/qwen3.6-flash",
    "gpt-5.6-luna (x2)": "openai/gpt-5.6-luna",
}
FREE_API = {"PSU-LLM/psu-gemma"}


def _n_clauses(answer):
    n = 0
    for sent in (s.strip() for s in _SENT.split(answer or "")):
        body = _CITE.sub("", sent).strip(" .:-*")
        n += sum(len(c) >= 8 for c in _clauses(body)) if body else 0
    return n


def _call(provider, model, messages):
    gen = TASKS["rag_answer"].gen
    t0 = time.perf_counter()
    res = (api_client if provider == "api" else ollama_client).chat(model, messages, gen)
    return res, (time.perf_counter() - t0)


def evaluate(name, model, provider, limit=None, log=print) -> dict:
    ctx = frozen_contexts()
    qs = questions()[:limit] if limit else questions()
    rows, lat, tokens, credits, errors = [], [], 0, 0, 0
    for q in qs:
        c = ctx[q["qid"]]
        msgs = prompts.rag_messages(q["question"], c["context"])
        try:
            res, sec = _call(provider, model, msgs)
        except Exception as e:
            errors += 1
            rows.append({"qid": q["qid"], "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        ans = res.text.strip()
        cite = parsing.citations(ans, len(c["refs"]))
        m = res.metrics or {}
        tok = (m.get("prompt_tokens") or 0) + (m.get("gen_tokens") or 0)
        tokens += tok
        credits += (api_client.credits(model, m.get("prompt_tokens") or 0, m.get("gen_tokens") or 0) or 0) if provider == "api" else 0
        lat.append(sec)
        row = {"qid": q["qid"], "answerable": q["answerable"], "abstained": cite["abstained"], "answer": ans,
               "seconds": round(sec, 2), "tokens": tok}
        if not cite["abstained"]:
            passages = [c["passages"][n - 1] for n in cite["cited"] if 1 <= n <= len(c["passages"])] or c["passages"]
            checked, dropped = verify_answer(q["question"], ans, passages)
            n = max(1, _n_clauses(ans))
            row.update(grounded=round(1 - dropped / n, 3), survives=checked is not None,
                       keyword=relevant(ans, q["expected_keywords"]) if q["answerable"] else None,
                       cited=cite["n_cited"] > 0 and not cite["invalid"])
        rows.append(row)
    ok = [r for r in rows if "error" not in r]
    ans_q = [r for r in ok if r["answerable"]]
    un_q = [r for r in ok if not r["answerable"]]
    answered = [r for r in ok if not r["abstained"]]
    summary = {
        "model": name, "model_id": model, "provider": provider, "n": len(qs), "errors": errors,
        "answered": round(sum(not r["abstained"] for r in ans_q) / max(1, len(ans_q)), 3),
        "refused": round(sum(r["abstained"] for r in un_q) / max(1, len(un_q)), 3),
        "grounded": round(statistics.mean(r["grounded"] for r in answered), 3) if answered else None,
        "keyword": round(sum(bool(r.get("keyword")) for r in ans_q) / max(1, len(ans_q)), 3),
        "cited": round(sum(bool(r.get("cited")) for r in answered) / max(1, len(answered)), 3),
        "sec_p50": round(statistics.median(lat), 2) if lat else None,
        "tokens": tokens, "credits": credits,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"answers_{provider}_{model.replace('/', '_').replace(':', '_')}.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    log(f"  {provider} {name}: ตอบ {summary['answered']} ปฏิเสธถูก {summary['refused']} "
        f"มีหลักฐาน {summary['grounded']} {summary['sec_p50']}s เครดิต {credits} error {errors}")
    return summary


def _unload(model):
    """ปล่อยโมเดล Local ออกจากหน่วยความจำก่อนโหลดตัวถัดไป (keep_alive ของบอทคือ 2 ชม. -> 5 ตัวค้างพร้อมกันเกิน 24 GB)"""
    import urllib.request
    from ..llm.config import OLLAMA_URL
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"model": model, "keep_alive": 0}).encode())
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


def run(provider, names=None, limit=None, log=print) -> list:
    models = LOCAL if provider == "local" else API
    rows = []
    for n in (names or models):
        rows.append(evaluate(n, models[n], provider, limit, log))
        if provider == "local":
            _unload(models[n])
    return rows
