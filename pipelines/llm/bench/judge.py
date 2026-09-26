"""วัดคุณภาพ explain_match (ข้อความการ์ดอธิบายคู่) — LLM-as-a-Judge + ตรวจด้วยกฎ

กรรมการ = gemma3:12b (คนละตระกูลกับโมเดลที่เขียน ลดอคติเข้าข้างตัวเอง)
rubric (1-5): faithfulness = ทุกข้อความมีหลักฐานในโปรไฟล์/CONTEXT, helpfulness = ช่วยให้ตัดสินใจ/เริ่มคุยได้, tone = ภาษาไทยเป็นกันเอง
กฎ (ไม่พึ่ง LLM): มีการอ้างอิง [n], พูดถึงรูปลักษณ์/สีผิว (ห้าม), เปิดเผยว่าอีกฝ่ายถูกรายงาน (ห้าม — ความเป็นส่วนตัว)
"""
import json
import random

from ...feedback import sensitive
from .. import ollama_client, parsing, tasks
from ..config import GenConfig

JUDGE_MODEL = "gemma3:12b"
REPORT_WORDS = ("ถูกรายงาน", "มีคนรายงาน", "report", "ร้องเรียน")
RUBRIC = {"type": "object", "required": ["faithfulness", "helpfulness", "tone", "unsupported_claims"],
          "properties": {"faithfulness": {"type": "integer", "minimum": 1, "maximum": 5},
                         "helpfulness": {"type": "integer", "minimum": 1, "maximum": 5},
                         "tone": {"type": "integer", "minimum": 1, "maximum": 5},
                         "unsupported_claims": {"type": "array", "items": {"type": "string"}}}}
JUDGE_PROMPT = """คุณเป็นกรรมการตรวจข้อความที่ chatbot หาคู่เขียนอธิบายว่าทำไมแนะนำ B ให้ A
ให้คะแนน 1-5:
- faithfulness: ทุกข้อความมีหลักฐานในข้อมูลด้านล่างหรือไม่ (5 = ไม่มีการแต่งเพิ่มเลย)
- helpfulness: ช่วยให้ A เข้าใจจุดเข้ากัน จุดระวัง และมีเคล็ดลับเริ่มคุยที่ใช้ได้จริง
- tone: ภาษาไทยเป็นกันเอง สุภาพ อ่านง่าย
unsupported_claims: ข้อความที่ไม่มีหลักฐาน (ถ้าไม่มีให้เป็น [])

=== ข้อมูลที่ chatbot ได้รับ ===
โปรไฟล์ A: {a}
โปรไฟล์ B: {b}
CONTEXT:
{ctx}

=== ข้อความที่ chatbot เขียน ===
{text}"""


def sample_pairs(ctx, n=15, seed=3):
    from ...hybrid import matcher
    rng = random.Random(seed)
    ids = [u for u, x in ctx.users.items() if x["consent"]["matching"]]
    out = []
    for uid in rng.sample(ids, n):
        top = matcher.rank(ctx, uid, "hybrid", top_k=1)
        if top:
            out.append((uid, top[0]["user_id"]))
    return out


def rule_checks(text, n_refs):
    cites = parsing.citations(text, n_refs)
    return {"cited": cites["n_cited"] > 0, "invalid_cite": bool(cites["invalid"]),
            "mentions_appearance": bool(sensitive.detect(text, mode="chat")),
            "reveals_report": any(w in text.lower() for w in REPORT_WORDS)}


def judge(a_text, b_text, ctx_text, explanation):
    res = ollama_client.chat(JUDGE_MODEL, [{"role": "user", "content": JUDGE_PROMPT.format(
        a=a_text, b=b_text, ctx=ctx_text, text=explanation)}], GenConfig(temperature=0, num_ctx=6144, num_predict=400), fmt=RUBRIC)
    obj = parsing.parse_json(res.text) or {}
    return {k: obj.get(k) for k in RUBRIC["properties"]}


def run(models, n=15, log=print):
    from ...hybrid.context import HybridContext
    from ...hybrid.retrievers import pair_context
    from ..context import build
    from ..config import TASKS
    ctx = HybridContext()
    pairs = sample_pairs(ctx, n)
    fmt = lambda u: "\n".join(v for k, v in ctx.users[u]["summaries"].items() if k.endswith("_text") and v)
    rows = []
    for model in models:
        cfg = TASKS["explain_match"].with_(model=model)
        for a, b in pairs:
            res = pair_context(ctx, a, b)
            out = tasks.explain_match(ctx.users[a], ctx.users[b], res, cfg)
            pack = build(res, cfg.context_budget)
            scores = judge(fmt(a), fmt(b), pack.text, out["explanation"])
            rows.append({"model": model, "a": a, "b": b, "explanation": out["explanation"], "llm": out["llm"],
                         "judge": scores, "rules": rule_checks(out["explanation"], len(out["refs"]))})
        log(f"  {model}: {len(pairs)} pairs judged", flush=True)
    return rows


def summarize(rows):
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        g[r["model"]].append(r)
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    out = []
    for m, rs in g.items():
        js = [r["judge"] for r in rs]
        out.append({"model": m, "n": len(rs),
                    "faithfulness": avg([j["faithfulness"] for j in js if j.get("faithfulness")]),
                    "helpfulness": avg([j["helpfulness"] for j in js if j.get("helpfulness")]),
                    "tone": avg([j["tone"] for j in js if j.get("tone")]),
                    "unsupported_per_card": avg([len(j.get("unsupported_claims") or []) for j in js]),
                    "cite_rate": avg([float(r["rules"]["cited"]) for r in rs]),
                    "appearance_leak": sum(r["rules"]["mentions_appearance"] for r in rs),
                    "report_leak": sum(r["rules"]["reveals_report"] for r in rs),
                    "p50_ms": sorted(r["llm"]["wall_ms"] for r in rs)[len(rs) // 2]})
    return out


if __name__ == "__main__":
    print(json.dumps(summarize(run(["scb10x/llama3.1-typhoon2-8b-instruct"], n=2)), ensure_ascii=False, indent=1))
