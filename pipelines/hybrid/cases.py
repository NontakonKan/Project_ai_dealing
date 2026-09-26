"""ค้นเคสจริงจากข้อมูลว่าแต่ละวิธีชนะ/แพ้ตรงไหน -> data/eval/hybrid/cases.md (ใช้ในรายงานหัวข้อ Graph RAG / Hybrid)

1. Red flag: ผู้สมัครที่ Dense จัดใน top-5 แต่ถูกรายงาน (>=3) ด้วย red flag ที่ผู้ใช้หลีกเลี่ยง -> Graph ตัดออก
2. ทฤษฎีขัดกัน: Dense top-5 ที่ attachment ขัดกันตามกฎ (เช่น anxious x avoidant) -> Graph หักคะแนน
3. ค่านิยม: Dense top-5 ที่ค่านิยมสำคัญขัดกัน (LLM อ่านจากข้อความ) -> Hybrid ดันลง
4. จุดอ่อนของ Graph: คำถามความรู้ที่ Graph ดึงไม่ได้แต่ Dense ดึงได้
"""
from datetime import date

from graph import scorer
from ..common.paths import DATA
from ..llm.bench.datasets import rag
from .context import HybridContext
from .matcher import dense_scores
from .config import HybridConfig
from .retrievers import DenseKnowledge, GraphKnowledge


def find(ctx, max_each=3):
    g, cfg = ctx.graph, HybridConfig()
    rf, theory, values = [], [], []
    stats = {"users": 0, "rf": 0, "theory": 0, "values": 0}
    for uid, u in ctx.users.items():
        if not u["consent"]["matching"]:
            continue
        stats["users"] += 1
        ds = dense_scores(ctx, uid, cfg)
        top = sorted(ds.items(), key=lambda x: -x[1]["score"])[:5]
        for rank, (cid, row) in enumerate(top, 1):
            info = scorer.pair(g, uid, cid, facts=True)
            hits = [h for h in info["redflags"] if h["avoider"] == uid]
            if hits:
                stats["rf"] += 1
                if len(rf) < max_each:
                    rf.append((uid, cid, rank, row["score"], hits))
            conflicts = [f for f in info["facts"] if "CONFLICTS_WITH" in f["text"] and "attach:" in "".join(f.get("concepts", []))]
            if conflicts:
                stats["theory"] += 1
                if len(theory) < max_each:
                    theory.append((uid, cid, rank, row["score"], conflicts[0]["text"]))
            sim = ctx.values_struct_sim(uid, cid)
            if sim < 0:
                stats["values"] += 1
                if len(values) < max_each:
                    values.append((uid, cid, rank, row["score"], sim))
    weak = []
    dk, gk = DenseKnowledge(ctx), GraphKnowledge(ctx)
    for q in rag():
        if q["answerable"] and not gk.retrieve(q["question"], 5).items:
            d = dk.retrieve(q["question"], 1).items
            weak.append((q["question"], d[0].id if d else "-"))
    return stats, rf, theory, values, weak


def render(stats, rf, theory, values, weak, ctx):
    lab = ctx.graph.label
    s = ctx.users
    out = [f"# เคสจริง: Dense vs Graph vs Hybrid ({date.today()})", "",
           f"สแกนผู้ใช้ {stats['users']} คน × ผู้สมัคร top-5 ของ Dense = {stats['users'] * 5} คู่", "",
           "| ปัญหาใน top-5 ของ Dense | จำนวนคู่ | ใครแก้ได้ |", "|---|---|---|",
           f"| ผู้สมัครถูกรายงาน red flag ที่ผู้ใช้หลีกเลี่ยง | {stats['rf']} | Graph (AVOIDS ∩ REPORTED_AS → ตัดออก) |",
           f"| attachment ขัดกันตามทฤษฎี | {stats['theory']} | Graph (HAS_TRAIT–CONFLICTS_WITH–HAS_TRAIT) |",
           f"| ค่านิยมสำคัญขัดกัน (เช่น อยากมีลูก vs ไม่อยาก) | {stats['values']} | Hybrid (LLM อ่านค่านิยมเป็นโครงสร้าง) |", "",
           "## 1. Red flag ที่ Dense มองไม่เห็น", ""]
    for uid, cid, rank, sc, hits in rf:
        h = hits[0]
        out += [f"- **{uid} → {cid}**: Dense จัดอันดับ {rank} (score {sc:.3f}) แต่ {cid} ถูกรายงานว่า *{lab(h['id'])}* "
                f"({h['report_count']} คน) ซึ่ง {uid} หลีกเลี่ยง (weight {h['weight']:.2f}) → Graph ตัดออก",
                f"  - persona ของ {cid}: {s[cid]['summaries']['persona_text'][:120]}…"]
    out += ["", "## 2. ความขัดกันเชิงทฤษฎี (multi-hop)", ""]
    for uid, cid, rank, sc, fact in theory:
        out.append(f"- **{uid} → {cid}**: Dense อันดับ {rank} (score {sc:.3f}) แต่กราฟพบ `{fact}` → Graph หักคะแนน (ข้อความไม่ได้บอกตรงๆ)")
    out += ["", "## 3. ค่านิยมขัดกัน (ข้อมูลนอก taxonomy)", ""]
    for uid, cid, rank, sc, sim in values:
        out += [f"- **{uid} → {cid}**: Dense อันดับ {rank} (score {sc:.3f}) ค่านิยมที่ LLM อ่านได้ขัดกัน (sim {sim:.2f})",
                f"  - {uid} อยากได้: {s[uid]['summaries'].get('values_want_text', '')}",
                f"  - {cid} บอกว่า: {s[cid]['summaries'].get('values_text', '')}"]
    out += ["", "## 4. จุดอ่อนของ Graph (Dense ช่วยได้)", "",
            "คำถามความรู้ที่ Graph หา concept ไม่เจอ (ไม่ได้อยู่ใน taxonomy) แต่ Dense ดึง chunk ได้:", ""]
    out += [f"- \"{q}\" → Dense: `{cid}`" for q, cid in weak]
    out += ["", "สรุป: Graph แม่นเรื่องกฎ/ความสัมพันธ์ที่มีโครงสร้าง, Dense ครอบคลุมเรื่องนอก taxonomy → Hybrid ใช้ทั้งสอง"]
    return "\n".join(out) + "\n"


def main():
    ctx = HybridContext()
    res = find(ctx)
    path = DATA / "eval" / "hybrid" / "cases.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(*res, ctx), encoding="utf-8")
    print(res[0], "->", path)


if __name__ == "__main__":
    main()
