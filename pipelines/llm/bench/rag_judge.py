"""ตรวจ "หลอน" ของโหมดตอบปรึกษา — รันเส้นทางเดียวกับบอท (routed -> gate -> rag_answer) แล้วให้กรรมการตรวจทุกคำตอบ

กรรมการ = gemma3:12b (คนละตระกูลกับ Typhoon ที่เขียนคำตอบ)
  supported      : ทุกประโยคมีหลักฐานใน CONTEXT ที่บอทได้รับ (ไม่ใช้ความรู้ภายนอก)
  on_question    : ตอบสิ่งที่ถามโดยตรง (ไม่หยิบเรื่องใกล้เคียงมาตอบแทน)
  unsupported_claims : ประโยคที่ไม่มีหลักฐาน
กฎ (ไม่พึ่ง LLM): คำถามที่คลังไม่มี (answerable=false) ต้องได้ "ไม่มีข้อมูล" / คำตอบต้องมี [n]

รัน: python -m pipelines.llm.bench.rag_judge [--limit N]   -> data/eval/rag_judge/<เวลา>/
"""
import argparse
import json
import time

from ...common.io_utils import write_json, write_jsonl
from ...common.paths import DATA
from .. import context as ctx_builder
from .. import ollama_client, tasks
from ..config import TASKS, GenConfig
from .datasets import rag

JUDGE_MODEL = "gemma3:12b"
RUBRIC = {"type": "object", "required": ["supported", "on_question", "unsupported_claims"],
          "properties": {"supported": {"type": "boolean"}, "on_question": {"type": "boolean"},
                         "unsupported_claims": {"type": "array", "items": {"type": "string"}}}}
PROMPT = """คุณเป็นกรรมการตรวจคำตอบของ chatbot ที่ต้องตอบจาก CONTEXT เท่านั้น
- supported: true ถ้าทุกประโยคในคำตอบมีหลักฐานใน CONTEXT (false ถ้ามีข้อมูล/คำแนะนำที่ CONTEXT ไม่ได้พูดถึง)
- on_question: true ถ้าคำตอบตอบสิ่งที่ถามโดยตรง (false ถ้าหยิบเรื่องอื่นที่แค่ใกล้เคียงมาตอบ)
- unsupported_claims: ประโยคที่ไม่มีหลักฐานใน CONTEXT (ไม่มีให้เป็น [])

คำถาม: {q}

CONTEXT:
{ctx}

คำตอบของ chatbot:
{a}"""


def bot_answer(retriever, question):
    """เส้นทางเดียวกับ app/flows/advice.py"""
    from ...hybrid import search
    found = search.find(retriever, question)
    res = found.result
    if not res.items:
        return {"answer": None, "gated": True, "context": ""}
    from ...hybrid.gate import verify_answer
    from .. import parsing
    from ...hybrid.query_expand import hint
    out = tasks.rag_answer(hint(question, found.topics), res)
    pack = ctx_builder.build(res, TASKS["rag_answer"].context_budget)
    answer, abstained, dropped = out["answer"], out["citations"]["abstained"], 0
    if not abstained:
        checked, dropped = verify_answer(question, answer, [it.text for it in res.items if it.id in out["refs"]])
        abstained = checked is None
        answer = checked or answer
    return {"answer": answer, "gated": False, "context": pack.text, "abstained": abstained, "dropped": dropped,
            "cited": [] if abstained else parsing.citations(answer, len(out["refs"]))["cited"]}


def judge(question, context, answer):
    res = ollama_client.chat(JUDGE_MODEL, [{"role": "user", "content": PROMPT.format(q=question, ctx=context, a=answer)}],
                             GenConfig(temperature=0, num_ctx=8192, num_predict=400), fmt=RUBRIC)
    try:
        return json.loads(res.text)
    except json.JSONDecodeError:
        return {"supported": None, "on_question": None, "unsupported_claims": ["(judge parse error)"]}


def main():
    from ...hybrid.context import HybridContext
    from ...hybrid.retrievers import RoutedKnowledge
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    retriever = RoutedKnowledge(HybridContext())
    rows = []
    for q in rag(args.limit):
        t0 = time.perf_counter()
        b = bot_answer(retriever, q["question"])
        refused = b["gated"] or b.get("abstained", False)
        row = {"qid": q["qid"], "question": q["question"], "answerable": q["answerable"], "style": q.get("style"),
               "refused": refused, "gated": b["gated"], "answer": b["answer"], "cited": b.get("cited", []),
               "dropped_sentences": b.get("dropped", 0),
               "ms": round((time.perf_counter() - t0) * 1000)}
        if not refused:
            row.update(judge(q["question"], b["context"], b["answer"]))
        rows.append(row)
        print(f"  {q['qid']} {'ปฏิเสธ' if refused else 'ตอบ'} "
              f"{'' if refused else ('✅' if row.get('supported') and row.get('on_question') else '⚠️')} {q['question'][:40]}", flush=True)

    ans = [r for r in rows if r["answerable"]]
    un = [r for r in rows if not r["answerable"]]
    answered = [r for r in rows if not r["refused"]]
    summary = {
        "n": len(rows),
        "answerable_answered": f"{sum(not r['refused'] for r in ans)}/{len(ans)}",
        "unanswerable_refused": f"{sum(r['refused'] for r in un)}/{len(un)}",
        "answered_supported": f"{sum(bool(r.get('supported')) for r in answered)}/{len(answered)}",
        "answered_on_question": f"{sum(bool(r.get('on_question')) for r in answered)}/{len(answered)}",
        "answered_with_citation": f"{sum(bool(r['cited']) for r in answered)}/{len(answered)}",
        "unsupported_claims": sum(len(r.get("unsupported_claims") or []) for r in answered),
        "judge": JUDGE_MODEL, "writer": TASKS["rag_answer"].model,
    }
    out = DATA / "eval" / "rag_judge" / time.strftime("%Y%m%d_%H%M%S")
    write_jsonl(out / "rows.jsonl", rows)
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1), "\n->", out)


if __name__ == "__main__":
    main()
