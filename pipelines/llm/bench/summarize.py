"""รวมผลรายแถว -> ตารางสรุปต่อ (model, variant[, mode])"""
import statistics
from collections import defaultdict

from .metrics import micro


def _pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def _mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else None


def _perf(rows):
    llm = [r["llm"] for r in rows]
    return {"n": len(rows),
            "p50_ms": _pct([m["wall_ms"] for m in llm], 0.5), "p95_ms": _pct([m["wall_ms"] for m in llm], 0.95),
            "gen_tok_s": _mean([m["gen_tok_s"] for m in llm]), "prompt_tok_s": _mean([m["prompt_tok_s"] for m in llm]),
            "prompt_tokens": _mean([m["prompt_tokens"] for m in llm]), "truncated": sum(m["truncated"] for m in llm)}


def extraction(rows, block_info) -> list:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["variant"])].append(r)
    out = []
    for (model, variant), rs in groups.items():
        val = lambda k: sum(r["validation"].get(k, 0) for r in rs)
        out.append({"model": model, "variant": variant, **micro([r["score"] for r in rs]), **_perf(rs),
                    "json_error": val("json_error"), "invalid_id": val("invalid_id"), "no_evidence": val("no_evidence"),
                    "false_rf": sum(r.get("false_rf", 0) for r in rs),
                    "guard_dropped": val("misclassified_appearance"), "guard_added": val("fallback_added"),
                    "guard_corrected": val("appearance_id_corrected") + val("red_flag_id_corrected"),
                    **block_info.get((model, variant), {})})
    return sorted(out, key=lambda x: (-x["f1"], x["p50_ms"] or 0))


def rag(rows, block_info) -> list:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["mode"], r["variant"])].append(r)
    out = []
    for (model, mode, variant), rs in groups.items():
        ans = [r for r in rs if r["answerable"]]
        out.append({"model": model, "mode": mode, "variant": variant,
                    "keyword_recall": _mean([r["score"]["keyword_recall"] for r in ans]),
                    "cite_rate": _mean([float(r["score"]["cited"]) for r in ans]),
                    "abstain_acc": _mean([float(r["score"]["correct_abstain"]) for r in rs]),
                    "ctx_tokens": _mean([r["context"]["used_tokens"] for r in rs]),
                    **_perf(rs), **block_info.get((model, variant), {})})
    return sorted(out, key=lambda x: (-(x["keyword_recall"] or 0), x["p50_ms"] or 0))


def to_markdown(rows, cols) -> str:
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "\n".join("| " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |" for r in rows)
