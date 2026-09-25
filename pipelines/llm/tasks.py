"""งานของ Local LLM (API เดียวที่ส่วนอื่นเรียกใช้)

ป้อนข้อมูลเข้า Dense/Graph:   extract_profile(), extract_unmatch()
ใช้ context จาก Dense/Graph/Hybrid: rag_answer(), explain_match()
ทุกฟังก์ชันคืน dict ที่มี "llm" (metric เวลา/token) เพื่อเก็บลง benchmark ได้ทันที
"""
from ..feedback import policy
from . import context as ctx
from . import guards, ollama_client, parsing, prompts, schemas
from .config import TASKS


def _fmt(cfg, schema_fn):
    return {"schema": schema_fn(), "json": "json"}.get(cfg.fmt)


def extract_profile(text, cfg=None) -> dict:
    cfg = cfg or TASKS["extract_profile"]
    res = ollama_client.chat(cfg.model, prompts.extract_messages(text, cfg.prompt), cfg.gen, _fmt(cfg, schemas.profile_schema))
    obj = parsing.parse_json(res.text)
    clean, stats = parsing.validate(obj, text, schemas.allowed_ids(schemas.PROFILE_FIELDS))
    stats.update(guards.drop_appearance_red_flags(clean))
    stats.update(guards.correct_appearance_ids(clean))
    stats.update(guards.correct_red_flag_ids(clean))
    return {"extracted": clean, "raw": res.text, "validation": dict(stats), "llm": res.metrics, "model": res.model}


def extract_unmatch(reason, cfg=None) -> dict:
    cfg = cfg or TASKS["extract_unmatch"]
    res = ollama_client.chat(cfg.model, prompts.unmatch_messages(reason, cfg.prompt), cfg.gen, _fmt(cfg, schemas.unmatch_schema))
    obj = parsing.parse_json(res.text)
    clean, stats = parsing.validate(obj, reason, schemas.allowed_ids(schemas.UNMATCH_FIELDS))
    stats.update(guards.drop_appearance_red_flags(clean, fields=("red_flags",)))
    stats.update(guards.correct_appearance_ids(clean))
    stats.update(guards.correct_red_flag_ids(clean, fields=("red_flags",)))
    stats.update(guards.fill_unmatch_appearance(clean, reason))
    for field in clean.values():
        for it in field:
            it["severity"] = min(1.0, max(0.0, float(it.get("severity") or 0.7)))
    return {"extracted": clean, "routed": policy.route_unmatch(clean), "raw": res.text, "validation": dict(stats),
            "llm": res.metrics, "model": res.model}


def rag_answer(query, retrieval, cfg=None) -> dict:
    """retrieval = RetrievalResult จาก Dense / Graph / Hybrid ตัวใดก็ได้"""
    cfg = cfg or TASKS["rag_answer"]
    pack = ctx.build(retrieval, cfg.context_budget)
    res = ollama_client.chat(cfg.model, prompts.rag_messages(query, pack.text, cfg.prompt), cfg.gen)
    return {"answer": res.text, "citations": parsing.citations(res.text, len(pack.refs)), "refs": pack.refs,
            "context": {"mode": retrieval.mode, "used_tokens": pack.used_tokens, "dropped": pack.dropped,
                        "kinds": pack.kinds, "retrieval_ms": round(retrieval.latency_ms, 2)},
            "llm": res.metrics, "model": res.model}


def explain_match(user_a, user_b, retrieval, cfg=None) -> dict:
    """user_a/user_b = โปรไฟล์จาก users.json, retrieval = context เรื่องความเข้ากันได้ของคู่นี้"""
    cfg = cfg or TASKS["explain_match"]
    pack = ctx.build(retrieval, cfg.context_budget)
    fmt_user = lambda u: f"{u['summaries']['persona_text']}\n{u['summaries']['preference_text']}\n{u['summaries']['avoid_text']}"
    res = ollama_client.chat(cfg.model, prompts.explain_messages(fmt_user(user_a), fmt_user(user_b), pack.text), cfg.gen)
    return {"explanation": res.text, "citations": parsing.citations(res.text, len(pack.refs)), "refs": pack.refs,
            "context": {"mode": retrieval.mode, "used_tokens": pack.used_tokens, "dropped": pack.dropped},
            "llm": res.metrics, "model": res.model}
