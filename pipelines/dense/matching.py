"""Two-way preference matching and negative-example penalty."""
from collections import defaultdict

from pipelines.common.io_utils import read_json, read_jsonl
from pipelines.common.paths import MOCK


def load_matching_data():
    return {u["user_id"]: u for u in read_json(MOCK / "users.json")}, read_jsonl(MOCK / "events.jsonl")


def eligible(a, b, events):
    if a["user_id"] == b["user_id"]:
        return False
    if not a.get("consent", {}).get("matching") or not b.get("consent", {}).get("matching"):
        return False
    da, db = a["demographic"], b["demographic"]
    if da["gender"] not in db["seeking"] or db["gender"] not in da["seeking"]:
        return False
    return not any(e["type"] in ("unmatch", "pass") and
                   {e["from_user"], e["about_user"]} == {a["user_id"], b["user_id"]}
                   for e in events)


def negative_examples(events):
    negatives = defaultdict(set)
    for e in events:
        if e["type"] == "unmatch":
            negatives[e["from_user"]].add(e["about_user"])
    return negatives


def rank(user_id, index, users=None, events=None, top_k=10, threshold=-1.0, penalty_weight=0.15):
    if users is None or events is None:
        users, events = load_matching_data()
    if user_id not in users:
        raise ValueError(f"Unknown user: {user_id}")
    if not users[user_id].get("consent", {}).get("matching"):
        raise ValueError("User has not consented to matching")
    negatives = negative_examples(events)
    blocked = {e["about_user"] if e["from_user"] == user_id else e["from_user"]
               for e in events if e["type"] in ("unmatch", "pass") and
               user_id in (e["from_user"], e["about_user"])}
    past = [n for n in negatives[user_id] if n in index.positions["persona"]]
    results = []
    for candidate_id, candidate in users.items():
        if candidate_id in blocked or not eligible(users[user_id], candidate, ()):
            continue
        if candidate_id not in index.positions["persona"] or user_id not in index.positions["preference"]:
            continue
        if user_id not in index.positions["persona"] or candidate_id not in index.positions["preference"]:
            continue
        forward = max(0.0, index.similarity("preference", user_id, "persona", candidate_id))
        reverse = max(0.0, index.similarity("preference", candidate_id, "persona", user_id))
        if min(forward, reverse) < threshold:
            continue
        base = 2 * forward * reverse / (forward + reverse) if forward + reverse else 0.0
        penalty = max((max(0.0, index.similarity("persona", candidate_id, "persona", n))
                       for n in past), default=0.0)
        results.append({"user_id": candidate_id, "score": round(base - penalty_weight * penalty, 6),
                        "base_score": round(base, 6), "forward": round(forward, 6),
                        "reverse": round(reverse, 6), "negative_penalty": round(penalty, 6)})
    return sorted(results, key=lambda x: (-x["score"], x["user_id"]))[:top_k]
