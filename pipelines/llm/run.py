"""CLI ของ Local LLM

  python -m pipelines.llm.run hardware                         # สเปกเครื่อง + โมเดลที่รันไหว
  python -m pipelines.llm.run demo                             # ลองทุก task (extract / unmatch / rag 3 โหมด)
  python -m pipelines.llm.run calibrate                        # วัดอัตรา ตัวอักษรไทย/token จริง
  python -m pipelines.llm.run bench --task extract_profile --models qwen2.5:3b,scb10x/llama3.2-typhoon2-3b-instruct \\
        --variants "fmt=schema,prompt=few_shot;fmt=json,prompt=zero_shot" --limit 30
  python -m pipelines.llm.run bench --task rag_answer --modes dense,graph,hybrid --variants "context_budget=1500;context_budget=3000"
"""
import argparse
import json
from datetime import datetime

from ..common.io_utils import read_jsonl, write_json, write_jsonl
from ..common.paths import DATA, PROCESSED
from ..retrieval.stubs import DenseStub, GraphStub, HybridStub
from . import hardware, ollama_client, tasks
from .bench import runner, summarize
from .config import TASKS

OUT = DATA / "eval" / "llm_bench"
EXTRACT_COLS = ["model", "variant", "f1", "precision", "recall", "p50_ms", "p95_ms", "gen_tok_s", "prompt_tokens",
                "json_error", "invalid_id", "no_evidence", "false_rf", "guard_dropped", "guard_added", "guard_corrected", "cold_load_ms", "peak_rss_mb", "gpu_mem_gb", "avg_cpu_pct", "other_models_loaded"]
RAG_COLS = ["model", "mode", "variant", "keyword_recall", "cite_rate", "abstain_acc", "ctx_tokens", "p50_ms", "p95_ms",
            "gen_tok_s", "cold_load_ms", "peak_rss_mb", "gpu_mem_gb"]


def _parse_value(v):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def parse_variants(s):
    if not s:
        return [{}]
    return [{k: _parse_value(v) for k, v in (kv.split("=", 1) for kv in part.split(",") if kv)} for part in s.split(";")]


def cmd_hardware(_):
    hw = hardware.detect()
    print(json.dumps(hw, ensure_ascii=False, indent=1))
    print(summarize.to_markdown(hardware.recommend(hw), ["name", "params", "quant", "size_gb", "est_mem_gb", "fits"]))


def cmd_demo(_):
    print(json.dumps(tasks.extract_profile("ชอบฟังเพลงชิล ทำกับข้าวกินเอง ไม่ชอบที่คนเยอะ ชอบคนใจเย็น ไม่เอาคนหายเงียบ"),
                     ensure_ascii=False, indent=1))
    print(json.dumps(tasks.extract_unmatch("ติดเพื่อนเกินไป เวลาไม่พอใจชอบหายไปเงียบๆ"), ensure_ascii=False, indent=1))
    q = "คนที่เป็น anxious กับ avoidant คบกันจะเป็นอย่างไร"
    dense, graph = DenseStub(), GraphStub()
    for r in (dense, graph, HybridStub(dense, graph)):
        out = tasks.rag_answer(q, r.retrieve(q))
        print(f"\n--- {r.mode} ---\n{out['answer']}\n{out['citations']} {out['context']} {out['llm']}")


def cmd_calibrate(args):
    model = args.models.split(",")[0] if args.models else TASKS["rag_answer"].model
    texts = [c["text"] for c in read_jsonl(PROCESSED / "book_chunks.jsonl")[:10]]
    chars = tokens = 0
    for t in texts:
        res = ollama_client.chat(model, [{"role": "user", "content": t}], TASKS["rag_answer"].gen.__class__(num_predict=1))
        chars, tokens = chars + len(t), tokens + res.metrics["prompt_tokens"]
    print(f"{model}: {chars / tokens:.2f} ตัวอักษร/token (ตั้ง CHARS_PER_TOKEN ใน context.py)")


def cmd_bench(args):
    models = args.models.split(",") if args.models else [TASKS[runner.CONFIG_KEY.get(args.task, args.task)].model]
    variants = parse_variants(args.variants)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT / f"{args.task}_{stamp}"
    print(f"bench {args.task}: {len(models)} models × {len(variants)} variants -> {out_dir}")
    if args.task == "explain_match":
        from .bench import judge
        rows = judge.run(models, n=args.limit or 15)
        table, cols = judge.summarize(rows), ["model", "n", "faithfulness", "helpfulness", "tone", "unsupported_per_card",
                                              "cite_rate", "appearance_leak", "report_leak", "p50_ms"]
    elif args.task == "rag_answer":
        modes = args.modes.split(",")
        rows, blocks = runner.run_rag(models, modes, variants, args.limit, retrievers=args.retrievers)
        table, cols = summarize.rag(rows, blocks), RAG_COLS
    else:
        rows, blocks = runner.run_extraction(args.task, models, variants, args.limit)
        table, cols = summarize.extraction(rows, blocks), EXTRACT_COLS
    write_jsonl(out_dir / "rows.jsonl", rows)
    write_json(out_dir / "summary.json", {"hardware": hardware.detect(), "task": args.task, "models": models,
                                          "retrievers": args.retrievers,
                                          "variants": variants, "limit": args.limit, "results": table})
    md = summarize.to_markdown(table, cols)
    (out_dir / "summary.md").write_text(md + "\n", encoding="utf-8")
    print(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hardware", "demo", "calibrate", "bench"])
    ap.add_argument("--task", default="extract_profile", choices=[*TASKS, *runner.CONFIG_KEY])
    ap.add_argument("--models")
    ap.add_argument("--variants", help='เช่น "fmt=schema,prompt=few_shot;fmt=json,prompt=zero_shot"')
    ap.add_argument("--modes", default="dense,graph,hybrid")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--retrievers", default="stub", choices=["stub", "real"], help="real = Dense/Graph/Hybrid ตัวจริง")
    args = ap.parse_args()
    {"hardware": cmd_hardware, "demo": cmd_demo, "calibrate": cmd_calibrate, "bench": cmd_bench}[args.cmd](args)


if __name__ == "__main__":
    main()
