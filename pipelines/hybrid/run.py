"""CLI ของ Hybrid

  python -m pipelines.hybrid.run match U002 --mode hybrid --top-k 5 [--explain]
  python -m pipelines.hybrid.run explain U002            # LLM อธิบายคู่อันดับ 1 (Local LLM)
  python -m pipelines.hybrid.run evaluate [--limit 50]   # Dense vs Graph vs Hybrid -> data/eval/hybrid/
  python -m pipelines.hybrid.run knowledge "คำถาม" --mode hybrid
ต้อง build Dense ก่อน: python -m pipelines.dense.run build
"""
import argparse
import json
from datetime import datetime

from ..common.io_utils import write_json
from ..common.paths import DATA
from ..llm.bench.summarize import to_markdown
from . import matcher
from .config import HybridConfig
from .context import HybridContext

EVAL_COLS = ["config", "K", "P@K", "R@K", "MRR", "nDCG@K", "Violation@K", "ms_per_user"]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match")
    m.add_argument("user_id")
    m.add_argument("--mode", default="hybrid", choices=["dense", "graph", "hybrid"])
    m.add_argument("--fusion", default="rrf", choices=["rrf", "weighted"])
    m.add_argument("--alpha", type=float, default=0.5)
    m.add_argument("--top-k", type=int, default=5)
    m.add_argument("--explain", action="store_true")
    x = sub.add_parser("explain")
    x.add_argument("user_id")
    e = sub.add_parser("evaluate")
    e.add_argument("--limit", type=int)
    sub.add_parser("knowledge-eval")
    k = sub.add_parser("knowledge")
    k.add_argument("query")
    k.add_argument("--mode", default="hybrid", choices=["dense", "graph", "hybrid", "routed"])
    k.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    ctx = HybridContext()

    if args.cmd == "match":
        cfg = HybridConfig(fusion=args.fusion, alpha=args.alpha)
        print(json.dumps(matcher.rank(ctx, args.user_id, args.mode, cfg, args.top_k, args.explain), ensure_ascii=False, indent=1))
    elif args.cmd == "explain":
        from ..llm import tasks
        from .retrievers import pair_context
        top = matcher.rank(ctx, args.user_id, "hybrid", top_k=1)[0]
        res = pair_context(ctx, args.user_id, top["user_id"])
        out = tasks.explain_match(ctx.users[args.user_id], ctx.users[top["user_id"]], res)
        print(json.dumps({"match": top, "context_ids": out["refs"], "explanation": out["explanation"],
                          "llm": out["llm"]}, ensure_ascii=False, indent=1))
    elif args.cmd == "knowledge-eval":
        from .knowledge_eval import evaluate as kevaluate
        rows = kevaluate(ctx)
        out = DATA / "eval" / "hybrid" / ("knowledge_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        write_json(out / "summary.json", {"dense": ctx.dense.manifest, "results": rows})
        md = to_markdown(rows, list(rows[0]))
        (out / "summary.md").write_text(md + "\n", encoding="utf-8")
        print(md, f"\n-> {out}")
    elif args.cmd == "knowledge":
        from .retrievers import DenseKnowledge, GraphKnowledge, HybridKnowledge, RoutedKnowledge
        r = {"dense": DenseKnowledge, "graph": GraphKnowledge, "hybrid": HybridKnowledge,
             "routed": RoutedKnowledge}[args.mode](ctx)
        res = r.retrieve(args.query)
        if args.llm:
            from ..llm import tasks
            out = tasks.rag_answer(args.query, res)
            print(out["answer"], "\n", out["citations"])
        else:
            for it in res.items:
                print(f"{it.kind:10} {it.score:<8} {it.id:32} {it.text[:80]}")
    else:
        from .evaluate import evaluate
        rows = evaluate(ctx, limit=args.limit)
        out = DATA / "eval" / "hybrid" / datetime.now().strftime("%Y%m%d_%H%M%S")
        write_json(out / "summary.json", {"graph_snapshot": ctx.graph.snapshot, "dense": ctx.dense.manifest, "results": rows})
        md = to_markdown(rows, EVAL_COLS)
        (out / "summary.md").write_text(md + "\n", encoding="utf-8")
        print(md, f"\n-> {out}")


if __name__ == "__main__":
    main()
