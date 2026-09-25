"""สร้าง Mock Dataset สำหรับ Data & Knowledge Base

Output (data/mock/):
  users.json               โปรไฟล์ผู้ใช้ (source of truth) + summaries สำหรับ embed
  events.jsonl             เหตุการณ์เลิกคุย/กดผ่าน/แมตช์สำเร็จ (append-only)
  chats.jsonl              แชทจำลอง + gold extraction (ใช้วัดความแม่นของ extractor)
  ground_truth_pairs.json  คู่ที่ควร/ไม่ควรแมตช์ (ใช้ใน Evaluation)
  data_report.json         สถิติคุณภาพข้อมูล

รัน: python3 -m pipelines.mock.run --n 300 --seed 42
"""
import argparse
import json
import random

from ..common.io_utils import write_json, write_jsonl
from ..common.paths import MOCK
from .chats import make_chats
from .config import TODAY
from .events import apply_feedback, make_events
from .ground_truth import make_ground_truth
from .report import report
from .summaries import build_summaries
from .users import make_user


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--chats", type=int, default=100)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    users = [make_user(i + 1, rng, TODAY) for i in range(args.n)]
    events = make_events(users, rng, TODAY)
    apply_feedback(users, events)
    for u in users:
        build_summaries(u)
    chats = make_chats(users, rng, min(args.chats, len(users)))
    gt = make_ground_truth(users, rng)
    stats = report(users, events, chats, gt)

    write_json(MOCK / "users.json", users)
    write_json(MOCK / "ground_truth_pairs.json", gt)
    write_json(MOCK / "data_report.json", stats)
    write_jsonl(MOCK / "events.jsonl", events)
    write_jsonl(MOCK / "chats.jsonl", chats)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
