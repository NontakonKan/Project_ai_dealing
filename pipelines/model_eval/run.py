"""รันการเปรียบเทียบโมเดล แล้วบันทึกผล + วาดกราฟ

  python -m pipelines.model_eval.run --groups sbert,bert,local       # ไม่เสียเครดิต
  python -m pipelines.model_eval.run --groups api --api psu-gemma     # เฉพาะ psu-gemma (ฟรี)
  python -m pipelines.model_eval.run --groups api                     # API ทั้ง 5 ตัว (เสียเครดิต)
  python -m pipelines.model_eval.run --plot-only                      # วาดกราฟจากผลที่บันทึกไว้

ผล: data/eval/model_compare/results_<group>.json + กราฟ .png ในโฟลเดอร์เดียวกัน
"""
import argparse
import json

from . import data

GROUPS = ("sbert", "bert", "local", "api")


def _save(group, rows):
    data.OUT.mkdir(parents=True, exist_ok=True)
    (data.OUT / f"results_{group}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", default="sbert,bert,local", help="เลือกจาก sbert,bert,local,api")
    ap.add_argument("--api", default="", help="ชื่อโมเดล API ที่จะรัน (คั่นด้วย ,) เว้นว่าง = ทั้ง 5 ตัว; จับคู่บางส่วนของชื่อได้")
    ap.add_argument("--limit", type=int, help="จำนวนคำถาม LLM (ค่าเริ่มต้น = ทั้งหมด 52 ข้อ)")
    ap.add_argument("--rebuild-contexts", action="store_true")
    ap.add_argument("--plot-only", action="store_true")
    args = ap.parse_args()
    if not args.plot_only:
        groups = [g for g in args.groups.split(",") if g in GROUPS]
        if {"local", "api"} & set(groups):
            data.frozen_contexts(rebuild=args.rebuild_contexts)
        for g in groups:
            print(f"== {g}")
            if g == "sbert":
                from .sbert import run
                rows = run()
            elif g == "bert":
                from .bert import run
                rows = run()
            else:
                from .llm import API, run
                names = None
                if g == "api" and args.api:
                    wanted = [w.strip().lower() for w in args.api.split(",") if w.strip()]
                    names = [n for n in API if any(w in n.lower() or w in API[n].lower() for w in wanted)]
                rows = run(g, names, args.limit)
                old = data.OUT / f"results_{g}.json"      # รันทีละบางตัวได้: รวมกับผลเดิมของตัวอื่น
                if old.exists():
                    keep = {r["model"]: r for r in json.loads(old.read_text(encoding="utf-8"))}
                    keep.update({r["model"]: r for r in rows})
                    rows = list(keep.values())
            _save(g, rows)
    from .plot import plot_all
    for f in plot_all():
        print("กราฟ:", f)


if __name__ == "__main__":
    main()
