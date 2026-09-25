"""สถิติคุณภาพข้อมูล mock"""
from collections import Counter


def report(users, events, chats, gt):
    c = lambda key: Counter(x["id"] for u in users for x in u["persona"][key])
    return {
        "n_users": len(users),
        "n_consented": sum(u["consent"]["matching"] for u in users),
        "archetype_dist": Counter(u["_archetype"] for u in users),
        "gender_dist": Counter(u["demographic"]["gender"] for u in users),
        "attachment_dist": Counter(u["persona"]["attachment_style"]["id"] for u in users),
        "trait_dist": c("traits"), "hobby_dist": c("hobbies"),
        "users_with_hidden_flags": sum(bool(u["_ground_truth_flags"]) for u in users),
        "event_type_dist": Counter(e["type"] for e in events),
        "avg_profile_completeness": round(sum(u["profile_completeness"] for u in users) / len(users), 3),
        "usable_reported_traits": sum(r["usable"] for u in users for r in u["reported_traits"]),
        "n_chats": len(chats), "chats_with_pii": sum(ch["has_pii"] for ch in chats),
        "gt_avg_relevant": round(sum(len(g["relevant"]) for g in gt) / len(gt), 2),
        "gt_avg_must_exclude": round(sum(len(g["must_exclude"]) for g in gt) / len(gt), 2),
    }
