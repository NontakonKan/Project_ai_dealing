"""Evaluate only here; ground truth is never loaded by retrieval code."""
from math import log2

from pipelines.common.io_utils import read_json
from pipelines.common.paths import MOCK
from .matching import load_matching_data, rank


def evaluate(index, top_ks=(5, 10, 20), thresholds=(0.0, 0.2), penalty_weights=(0.0, 0.15)):
    truth = read_json(MOCK / "ground_truth_pairs.json")
    users, events = load_matching_data()
    rows = truth.values() if isinstance(truth, dict) else truth
    rows = [r for r in rows if r["user_id"] in users and r["user_id"] in index.positions["persona"]]
    report = []
    for k in top_ks:
        for threshold in thresholds:
            for weight in penalty_weights:
                precision = recall = mrr = ndcg = violations = 0.0
                used = 0
                for row in rows:
                    relevant = {x["user_id"] for x in row.get("relevant", [])}
                    excluded = set(row.get("must_exclude", []))
                    if not relevant:
                        continue
                    found = rank(row["user_id"], index, users, events, k, threshold, weight)
                    ids = [x["user_id"] for x in found]
                    hits = [int(uid in relevant) for uid in ids]
                    precision += sum(hits) / k
                    recall += sum(hits) / len(relevant)
                    mrr += next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0)
                    dcg = sum(hit / log2(i + 2) for i, hit in enumerate(hits))
                    ideal = sum(1 / log2(i + 2) for i in range(min(k, len(relevant))))
                    ndcg += dcg / ideal if ideal else 0
                    violations += len(excluded.intersection(ids)) / k
                    used += 1
                if used:
                    report.append({"top_k": k, "threshold": threshold, "penalty_weight": weight,
                                   "queries": used, "precision_at_k": round(precision / used, 4),
                                   "recall_at_k": round(recall / used, 4), "mrr": round(mrr / used, 4),
                                   "ndcg_at_k": round(ndcg / used, 4),
                                   "violation_at_k": round(violations / used, 4)})
    return report
