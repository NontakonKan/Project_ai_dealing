"""ชุดทดสอบเหตุผลเลิกคุยแบบ held-out: สำนวนที่ระบบไม่เคยเห็น

ปัญหาเดิม: unmatch_sensitive.json เขียนจาก aliases ใน taxonomy -> คะแนนสูงเกินจริง
วิธีนี้:  ให้ LLM อีกตระกูล (gemma3:12b) เขียนเหตุผลภาษาพูดจาก "คำอธิบายภาษาอังกฤษ" ของพฤติกรรม
          -> ไม่เห็น aliases ไทย, แล้วตัดประโยคที่บังเอิญมี alias ทิ้ง (กันรั่ว)
ข้อจำกัด: ยังเป็นข้อความจาก LLM ไม่ใช่คนจริง (ควรให้คนตรวจ/เพิ่มภายหลัง)

รัน: python -m pipelines.eval_data.heldout_unmatch --per 2
"""
import argparse
import random

from ..common import taxonomy
from ..common.io_utils import write_json
from ..common.paths import DATA
from ..llm import ollama_client
from ..llm.config import GenConfig

GEN_MODEL = "gemma3:12b"
DESCRIBE = {  # คำอธิบายเป็นภาษาอังกฤษ (ไม่ใช้คำไทยจาก taxonomy)
    "rf:stonewalling": "during conflicts the partner shuts down, gives the silent treatment and refuses to talk it through",
    "rf:friend_priority": "the partner always puts hanging out with friends first and never makes time for you",
    "rf:possessive": "the partner is controlling and jealous, checks your phone, wants to know where you are all the time",
    "rf:ghosting": "the partner suddenly stopped replying and disappeared without saying goodbye",
    "rf:gaslighting": "the partner denies things they clearly said and makes you doubt your own memory",
    "rf:disrespect": "the partner insults you, talks down to you and belittles you",
    "rf:dishonest": "the partner lies and was secretly talking to other people",
    "rf:hot_temper": "the partner explodes with anger over small things and yells",
    "rf:inconsistent": "the partner is warm one day and cold the next, keeps cancelling plans",
    "rf:no_boundaries": "the partner does not respect personal space, calls nonstop and shows up uninvited",
    "body:slim": "the other person is too skinny for your taste",
    "body:curvy": "the other person is heavier / chubbier than your type",
    "body:athletic": "the other person is too muscular / bulky for your taste",
    "skin:dark": "the other person's skin tone is darker than your preference",
    "skin:fair": "the other person's skin is paler than your preference",
    "hygiene:self_care": "the other person had bad body odor / did not take care of hygiene",
}
FIELD = lambda tid: "red_flags" if tid.startswith("rf:") else "hygiene" if tid.startswith("hygiene:") else "appearance"
PROMPT = """You write realistic Thai LINE chat messages. A Thai university student tells a dating chatbot why they
stopped talking to a match. Write ONE short casual Thai message (1-2 sentences, informal, like real chat) that
expresses ALL of these reasons in your own words:
{reasons}
Do NOT use these words: {banned}
Output only the Thai message."""


def _aliases(tid):
    return [a for a in taxonomy.aliases().get(tid, []) + [taxonomy.labels()[tid]] if "/" not in a]


def generate(per=2, combos=8, seed=7, log=print):
    rng = random.Random(seed)
    targets = [[t] for t in DESCRIBE for _ in range(per if t.startswith("rf:") else 1)]
    rfs, looks = [t for t in DESCRIBE if t.startswith("rf:")], [t for t in DESCRIBE if not t.startswith("rf:")]
    targets += [[rng.choice(rfs), rng.choice(looks)] for _ in range(combos)]
    rows, dropped = [], 0
    for i, ids in enumerate(targets):
        banned = sorted({a for t in ids for a in _aliases(t)})
        prompt = PROMPT.format(reasons="\n".join(f"- {DESCRIBE[t]}" for t in ids), banned=", ".join(banned))
        for attempt in range(3):
            text = ollama_client.chat(GEN_MODEL, [{"role": "user", "content": prompt}],
                                      GenConfig(temperature=0.9, num_predict=120, seed=seed + i * 10 + attempt)).text.strip().strip('"')
            if not any(a in text for a in banned):
                break
            dropped += 1
        else:
            continue
        gold = {"red_flags": [], "appearance": [], "hygiene": []}
        for t in ids:
            gold[FIELD(t)].append(t)
        rows.append({"id": f"H{i + 1:02d}", "input": text, "gold": gold, "generated_by": GEN_MODEL})
        log(f"  H{i + 1:02d} {ids} -> {text}")
    return rows, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=2)
    ap.add_argument("--combos", type=int, default=8)
    args = ap.parse_args()
    rows, dropped = generate(args.per, args.combos)
    write_json(DATA / "eval" / "unmatch_heldout.json", rows)
    print(f"{len(rows)} ข้อ (ตัดประโยคที่มี alias ทิ้ง {dropped} ครั้ง) -> data/eval/unmatch_heldout.json")


if __name__ == "__main__":
    main()
