"""CLI: python -m pipelines.dense.run {build,match,knowledge,evaluate}."""
import argparse
import json

from .embedding import DEFAULT_MODEL
from .index import DEFAULT_INDEX, DenseIndex, build
from .matching import rank
from .evaluation import evaluate
from .rag import context_for_match, answer_with_llm


def main():
    parser = argparse.ArgumentParser(description="Dense RAG for Project_ai_dealing")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build")
    b.add_argument("--model", default=DEFAULT_MODEL)
    m = commands.add_parser("match")
    m.add_argument("user_id")
    m.add_argument("--top-k", type=int, default=5)
    m.add_argument("--threshold", type=float, default=0.0)
    m.add_argument("--penalty-weight", type=float, default=0.15)
    m.add_argument("--llm", action="store_true")
    k = commands.add_parser("knowledge")
    k.add_argument("query")
    k.add_argument("--top-k", type=int, default=5)
    k.add_argument("--threshold", type=float, default=0.0)
    k.add_argument("--category")
    k.add_argument("--concept")
    k.add_argument("--llm", action="store_true")
    e = commands.add_parser("evaluate")
    e.add_argument("--top-ks", type=int, nargs="+", default=[5, 10, 20])
    e.add_argument("--thresholds", type=float, nargs="+", default=[0.0, 0.2])
    e.add_argument("--penalty-weights", type=float, nargs="+", default=[0.0, 0.15])
    args = parser.parse_args()
    if args.command == "build":
        output = build(args.index, args.model)
    else:
        index = DenseIndex(args.index)
        if args.command == "match":
            output = context_for_match(args.user_id, index, args.top_k, args.threshold, args.penalty_weight) if args.llm else rank(args.user_id, index, top_k=args.top_k, threshold=args.threshold, penalty_weight=args.penalty_weight)
            if args.llm:
                output = {"context": output, "llm": answer_with_llm(output)}
        elif args.command == "knowledge":
            output = index.search("knowledge", args.query, args.top_k, args.threshold, args.category, args.concept)
            if args.llm:
                context = {"question": args.query, "knowledge": output}
                output = {"context": context, "llm": answer_with_llm(context)}
        else:
            output = evaluate(index, args.top_ks, args.thresholds, args.penalty_weights)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
