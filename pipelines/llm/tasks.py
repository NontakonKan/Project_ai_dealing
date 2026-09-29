"""งานของ Local LLM (API เดียวที่ส่วนอื่นเรียกใช้)

ป้อนข้อมูลเข้า Dense/Graph:   extract_profile(), extract_unmatch()
ใช้ context จาก Dense/Graph/Hybrid: rag_answer(), explain_match()
ทุกฟังก์ชันคืน dict ที่มี "llm" (metric เวลา/token) เพื่อเก็บลง benchmark ได้ทันที
"""
import re
from ..feedback import policy
from . import context as ctx
from . import guards, parsing, prompts, providers, schemas
from .config import TASKS


def _fmt(cfg, schema_fn):
    return {"schema": schema_fn(), "json": "json"}.get(cfg.fmt)


def extract_profile(text, cfg=None) -> dict:
    cfg = cfg or TASKS["extract_profile"]
    res = providers.chat(cfg.model, prompts.extract_messages(text, cfg.prompt), cfg.gen, _fmt(cfg, schemas.profile_schema), fallback=cfg.fallback or None)
    obj = parsing.parse_json(res.text)
    clean, stats = parsing.validate(obj, text, schemas.allowed_ids(schemas.PROFILE_FIELDS))
    stats.update(guards.drop_appearance_red_flags(clean))
    stats.update(guards.correct_appearance_ids(clean))
    stats.update(guards.correct_red_flag_ids(clean))
    stats.update(guards.drop_invalid_avoids(clean, text))
    stats.update(guards.drop_faculty_hallucinations(clean, text))
    return {"extracted": clean, "raw": res.text, "validation": dict(stats), "llm": res.metrics, "model": res.model}


def extract_unmatch(reason, cfg=None) -> dict:
    cfg = cfg or TASKS["extract_unmatch"]
    res = providers.chat(cfg.model, prompts.unmatch_messages(reason, cfg.prompt), cfg.gen, _fmt(cfg, schemas.unmatch_schema), fallback=cfg.fallback or None)
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


def rag_answer(query, retrieval, cfg=None, history=None) -> dict:
    """retrieval = RetrievalResult จาก Dense / Graph / Hybrid ตัวใดก็ได้"""
    cfg = cfg or TASKS["rag_answer"]
    pack = ctx.build(retrieval, cfg.context_budget)
    res = providers.chat(cfg.model, prompts.rag_messages(query, pack.text, cfg.prompt, history=history), cfg.gen, fallback=cfg.fallback or None)
    return {"answer": res.text, "citations": parsing.citations(res.text, len(pack.refs)), "refs": pack.refs,
            "context": {"mode": retrieval.mode, "used_tokens": pack.used_tokens, "dropped": pack.dropped,
                        "kinds": pack.kinds, "retrieval_ms": round(retrieval.latency_ms, 2)},
            "llm": res.metrics, "model": res.model}


def rewrite_query(query, kb_topics=(), cfg=None) -> list:
    """-> คำถามทั่วไป ไม่เกิน 3 แบบ (ใช้ค้นเท่านั้น ไม่ใช่คำตอบ) — ด่านความเกี่ยวข้องใช้คะแนนสูงสุดของทุกแบบ"""
    cfg = cfg or TASKS["rewrite_query"]
    res = providers.chat(cfg.model, prompts.search_rewrite_messages(query, kb_topics), cfg.gen, fallback=cfg.fallback or None)
    lines = (re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", l).strip() for l in res.text.splitlines())
    return [l for l in lines if 3 <= len(l) <= 100][:3]


def explain_match(user_a, user_b, retrieval, cfg=None) -> dict:
    """user_a/user_b = โปรไฟล์จาก users.json, retrieval = context เรื่องความเข้ากันได้ของคู่นี้"""
    cfg = cfg or TASKS["explain_match"]
    pack = ctx.build(retrieval, cfg.context_budget)
    fmt_user = lambda u: f"{u['summaries']['persona_text']}\n{u['summaries']['preference_text']}\n{u['summaries']['avoid_text']}"
    res = providers.chat(cfg.model, prompts.explain_messages(fmt_user(user_a), fmt_user(user_b), pack.text), cfg.gen, fallback=cfg.fallback or None)
    return {"explanation": res.text, "citations": parsing.citations(res.text, len(pack.refs)), "refs": pack.refs,
            "context": {"mode": retrieval.mode, "used_tokens": pack.used_tokens, "dropped": pack.dropped},
            "llm": res.metrics, "model": res.model}


class AmbiguousFollowup(ValueError):
    """The supplied context cannot resolve the follow-up."""


def rewrite_question(query, history, cfg=None):
    cfg = cfg or TASKS["rag_answer"]
    from dataclasses import replace
    gen = replace(cfg.gen, temperature=0, num_predict=200)
    result = providers.chat(cfg.model, prompts.rewrite_messages(query, history), gen,
                            fallback=cfg.fallback or None)
    question = result.text.strip()
    if question.upper().strip(". ") == "UNKNOWN":
        raise AmbiguousFollowup("Ambiguous follow-up question")
    if not question or len(question) > 500 or result.metrics.get("truncated"):
        raise ValueError("Invalid rewritten question")
    return question


def summarize_memory(rows, existing):
    """Use local extraction model for personal memory, regardless of API overrides."""
    import json
    from dataclasses import replace
    from .config import QWEN_7B
    cfg = TASKS["extract_profile"]
    model = cfg.model if not providers.is_api(cfg.model) else (cfg.fallback or QWEN_7B)
    if providers.is_api(model):
        model = QWEN_7B
    compact, used = [], 0
    for fact in existing:
        item = {k: fact[k] for k in ('key', 'summary')}
        cost = ctx.estimate_tokens(json.dumps(item, ensure_ascii=False))
        if used + cost > 1000:
            break
        compact.append(item)
        used += cost
    try:
        result = providers.chat(model, prompts.memory_messages(rows, compact),
                                replace(cfg.gen, num_ctx=8192, num_predict=1200), fmt="json")
    except Exception as e:
        if cfg.model != model and (providers.is_api(cfg.model) or cfg.fallback):
            fallback_model = cfg.fallback if cfg.fallback and cfg.fallback != model else cfg.model
            result = providers.chat(fallback_model, prompts.memory_messages(rows, compact),
                                    replace(cfg.gen, num_ctx=8192, num_predict=1200), fmt="json")
        else:
            raise e
    if result.metrics.get('truncated'):
        raise ValueError('Truncated memory update')
    return json.loads(result.text)['changes']


def recall_answer(query, memories):
    from dataclasses import replace
    from .config import QWEN_7B
    cfg = TASKS['extract_profile']
    model = cfg.model if not providers.is_api(cfg.model) else QWEN_7B
    result = providers.chat(model, prompts.recall_messages(query, memories),
                            replace(cfg.gen, num_ctx=4096, num_predict=400))
    if not result.text.strip() or result.metrics.get('truncated'):
        raise ValueError('Invalid recall answer')
    return result.text.strip()
