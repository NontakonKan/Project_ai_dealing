"""วัดตัวแยกเจตนา: กฎคำตายตัว (เดิม) vs SBERT / BM25 / รวม / รวม + LLM

ชุดทดสอบเป็นประโยคที่ "ไม่อยู่ใน" ตัวอย่างของ intent_model.INTENTS (สำนวนต่าง / ภาษาพูด / พิมพ์สั้น)
เทียบที่ปลายทางจริง (followup -> ask_advice) เพราะบอทแยกแค่นั้น

รัน: python -m app.intent_eval [--no-llm]
"""
import argparse
import json
import time
from collections import Counter

from .intent_model import ROUTE, classify

TEST = {
    "find_match": ["ช่วยหาคนที่เหมาะกับผมหน่อย", "มีใครน่าสนใจแนะนำบ้าง", "อยากเจอคนใหม่ๆ", "ขอคนที่เข้ากันได้หน่อยครับ",
                   "เปิดดูคู่แนะนำ", "มีคนโสดแนะนำไหม"],
    "show_profile": ["ข้อมูลผมที่บันทึกไว้", "ดูสิ่งที่บอทรู้เกี่ยวกับเรา", "โปรไฟล์ผมเป็นยังไงบ้าง", "เปิดประวัติของฉันหน่อย",
                     "ระบบเก็บอะไรของผมไว้"],
    "delete_me": ["ส่งลบโปรไฟล์", "ลบโปรไฟล์", "ลบข้อมูลทิ้งทั้งหมด", "ไม่ใช้แล้ว ลบให้ด้วย", "ขอให้ลืมข้อมูลของผมทั้งหมด",
                  "ลบแอคเคานต์", "remove my data"],
    "unmatch": ["ไม่อยากคุยกับคนที่แนะนำแล้ว", "คนนี้ไม่ใช่สเปค ขอผ่าน", "หยุดคุยกับเขาแล้ว", "ไม่ไปต่อกับคนนี้นะ",
                "ขอยกเลิกการจับคู่"],
    "recall_memory": ["จำที่ผมเล่าเมื่อวานได้ป่าว", "เคยบอกไปแล้วว่าชอบอะไร จำได้ไหม", "คราวที่แล้วเราคุยอะไรกันนะ",
                      "ก่อนหน้านี้ผมบอกคณะไหนไป"],
    "ask_advice": ["ส่งข้อความหาคนที่ชอบตอนดึกดีไหม", "แฟนเช็คโทรศัพท์ตลอด ปกติไหม", "love bombing คืออะไร",
                   "ทำไมเลิกกันแล้วยังคิดถึง", "คุยกันครั้งแรกควรชวนไปดูหนังไหม", "ตรวจเอชไอวีต้องเตรียมตัวยังไง",
                   "จะบอกเลิกยังไงให้เจ็บน้อยที่สุด", "คนขี้หึงแก้ยังไง"],
    "followup": ["ขอตัวอย่างเพิ่มหน่อย", "ข้อสามหมายความว่าไง", "ถ้าเขายังเงียบอยู่ล่ะ", "ช่วยอธิบายอีกทีได้ไหม"],
    "chat": ["หวัดดี", "ผมชอบฟังเพลงชิลๆ", "อยากได้แฟนผิวแทน", "เปลี่ยนใจอยากได้คนเรียนวิศวะ", "ผมเป็นคนร่าเริง",
             "วันนี้ฝนตกเบื่อจัง", "ขอบใจนะ", "ไม่ชอบคนเจ้าชู้", "ผมอายุ 21", "ชอบคนที่รักสัตว์"],
}


# ชุดสด: เขียนหลังปรับ intent_model เสร็จแล้ว และรันครั้งเดียว (ไม่ใช้ปรับค่าใดๆ) -> ตัวเลขที่รายงานได้ไม่ลำเอียง
TEST_FRESH = {
    "find_match": ["ขอดูคนที่แมตช์กับผม", "มีใครให้ลองคุยบ้าง", "เสนอคนให้หน่อยสิ"],
    "show_profile": ["ขอดูว่าบอทเก็บอะไรของฉันไว้", "ข้อมูลส่วนตัวของผมในระบบ", "ตอนนี้โปรไฟล์ผมมีอะไร"],
    "delete_me": ["เคลียร์ข้อมูลของผมออกให้หมด", "ขอลบตัวเองออกจากแอป", "ไม่อยากให้เก็บข้อมูลแล้ว ลบเลย"],
    "unmatch": ["คนที่แนะนำมาไม่โอเค ขอเลิก", "ไม่อยากคุยกับคู่นี้แล้ว", "ขอข้ามคนนี้"],
    "recall_memory": ["ยังจำได้ไหมที่ผมเคยเล่าเรื่องงานอดิเรก", "ผมเคยบอกสเปคไว้ว่ายังไงนะ"],
    "ask_advice": ["คบกันมานานแต่รู้สึกเบื่อ ควรทำยังไง", "โดนเท ควรทักกลับไหม", "แฟนติดเกมมาก ปรึกษาหน่อย",
                   "situationship คืออะไร", "นัดเดตแรกควรคุยเรื่องอะไรดี"],
    "followup": ["แล้วถ้าเขาโกรธล่ะ", "ขยายความอีกหน่อยได้ไหม"],
    "chat": ["ผมชอบวิ่งตอนเช้า", "เราเป็นคนขี้อายนิดนึง", "ชอบคนตัวสูง", "ฮ่าๆ ตลกดี", "ผมเรียนปีสาม"],
}


def rules_baseline(t):
    """กฎคำตายตัวแบบเดิม (ก่อน merge: คำสั่ง -> มีคำถาม = ปรึกษา -> ที่เหลือ = คุยเล่น)"""
    t = t.strip().lower()
    if any(k in t for k in ("ลบข้อมูลของฉัน", "ลบข้อมูลฉัน", "ลบบัญชี")):
        return "delete_me"
    if any(k in t for k in ("โปรไฟล์ของฉัน", "โปรไฟล์ฉัน", "จำอะไรเกี่ยวกับ", "ข้อมูลของฉัน")):
        return "show_profile"
    if any(k in t for k in ("หาคู่", "หาคน", "แนะนำคน", "แนะนำคู่", "จับคู่", "match", "หาแฟน")):
        return "find_match"
    if any(k in t for k in ("เลิกคุย", "ไม่คุยต่อ", "ไม่ไปต่อ")):
        return "unmatch"
    if any(k in t for k in ("จำได้ไหม", "จำได้มั้ย", "เคยบอก", "เคยเล่า", "ครั้งก่อน", "คราวก่อน", "ก่อนหน้านี้", "วันก่อน")):
        return "recall_memory"
    if any(k in t for k in ("?", "ไหม", "มั้ย", "อย่างไร", "ยังไง", "ทำไง", "คืออะไร", "ควร", "ทำไม", "แบบไหน", "ปรึกษา")):
        return "ask_advice"
    return "chat"


CONFIGS = {
    "กฎคำตายตัว (เดิม)": lambda t: (rules_baseline(t), {}),
    "BM25 อย่างเดียว": lambda t: classify(t, use_llm=False, use_dense=False),
    "SBERT อย่างเดียว": lambda t: classify(t, use_llm=False, use_bm25=False),
    "SBERT + BM25": lambda t: classify(t, use_llm=False),
    "SBERT + BM25 + LLM (ใช้จริง)": lambda t: classify(t),
}


def evaluate(names, test=None):
    rows = [(exp, t) for exp, ts in (test or TEST).items() for t in ts]
    report = {}
    for name in names:
        t0, ok, wrong, by = time.time(), 0, [], Counter()
        for exp, t in rows:
            got, info = CONFIGS[name](t)
            by[info.get("by", "rule")] += 1
            want, pred = ROUTE.get(exp, exp), ROUTE.get(got, got)
            ok += want == pred
            if want != pred:
                wrong.append(f"{t} → {pred} (ควรเป็น {want})")
        report[name] = {"accuracy": round(ok / len(rows), 3), "correct": ok, "n": len(rows),
                        "ms_per_msg": round((time.time() - t0) * 1000 / len(rows)), "decided_by": dict(by), "wrong": wrong}
        print(f"{name:32} {ok}/{len(rows)} = {ok / len(rows):.1%}  {report[name]['ms_per_msg']} ms/ข้อความ  {dict(by)}")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ใช้ชุดสด (รายงานผล) แทนชุดที่ใช้ปรับค่า")
    args = ap.parse_args()
    names = [n for n in CONFIGS if not (args.no_llm and "LLM" in n)]
    report = evaluate(names, TEST_FRESH if args.fresh else TEST)
    from pipelines.common.paths import DATA
    out = DATA / "eval" / ("intent_eval_fresh.json" if args.fresh else "intent_eval.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
