"""ให้ LLM อ่าน "ค่านิยม" จากข้อความ -> ข้อมูลมีโครงสร้าง (แก้จุดอ่อนของ embedding เรื่องความหมายตรงข้าม)

ที่มา: bge-m3 แยก "อยากมีลูก" กับ "ไม่อยากมีลูก" ได้แย่ (cosine 0.70 vs 0.63) -> Hybrid ได้ P@5 0.25
       ถ้าอ่านค่านิยมได้ถูก 100% เพดาน = 0.313 -> ลองให้ LLM อ่านแทน แล้วเทียบกับเพดาน
ผลเก็บที่ data/processed/values_structured.json (รันครั้งเดียว ใช้ซ้ำได้)

รัน: python -m pipelines.hybrid.values_extract [--model qwen2.5:latest]
"""
import argparse
import json
import time

from ..common.io_utils import read_json, write_json
from ..common.paths import MOCK, PROCESSED
from ..llm import ollama_client
from ..llm.config import GenConfig

OUT = PROCESSED / "values_structured.json"
DIMS = {"family": ["want_kids", "no_kids"], "place": ["city", "hometown"],
        "money": ["saver", "spender"], "pets": ["pet_lover", "no_pets"]}
DESC = ("family: want_kids=อยากมีลูก / no_kids=ไม่อยากมีลูก\n"
        "place: city=อยากอยู่เมืองใหญ่ / hometown=อยากอยู่บ้านเกิด ต่างจังหวัด บ้านสวน\n"
        "money: saver=ประหยัด เก็บออม / spender=ใช้เงินตามใจ\n"
        "pets: pet_lover=ชอบ/อยากเลี้ยงสัตว์ / no_pets=ไม่เลี้ยง แพ้ขนสัตว์")
SCHEMA = {"type": "object", "required": list(DIMS),
          "properties": {d: {"type": "string", "enum": v + ["unknown"]} for d, v in DIMS.items()}}
PROMPT = "อ่านข้อความแล้วระบุค่านิยมแต่ละด้าน ถ้าข้อความไม่ได้พูดถึงด้านไหนให้ตอบ unknown ห้ามเดา\n{desc}\n\nข้อความ: {text}"


def extract(text, model):
    if not text.strip():
        return {d: "unknown" for d in DIMS}
    res = ollama_client.chat(model, [{"role": "user", "content": PROMPT.format(desc=DESC, text=text)}],
                             GenConfig(temperature=0, num_ctx=1024, num_predict=80), fmt=SCHEMA)
    try:
        obj = json.loads(res.text)
    except json.JSONDecodeError:
        obj = {}
    return {d: obj.get(d, "unknown") if obj.get(d) in DIMS[d] + ["unknown"] else "unknown" for d in DIMS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:latest")
    args = ap.parse_args()
    users, out, t0 = read_json(MOCK / "users.json"), {}, time.perf_counter()
    for i, u in enumerate(users):
        s = u["summaries"]
        out[u["user_id"]] = {"self": extract(s.get("values_text", ""), args.model),
                             "wants": extract(s.get("values_want_text", ""), args.model)}
        if i % 50 == 0:
            print(f"  {i}/{len(users)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    # ความแม่นเทียบค่านิยมจริงที่ถูกพูดถึง (เฉพาะรายงาน — ไม่ได้ใช้ในการจับคู่)
    tp = fp = fn = 0
    for u in users:
        truth = u["_ground_truth_values"]["truth"]
        for d, v in out[u["user_id"]]["self"].items():
            said = any(p in u["summaries"].get("values_text", "") for p in __import__("pipelines.mock.values", fromlist=["VALUES"]).VALUES[d][truth[d]])
            if v != "unknown":
                tp += v == truth[d]
                fp += v != truth[d]
            elif said:
                fn += 1
    write_json(OUT, {"model": args.model, "seconds": round(time.perf_counter() - t0, 1),
                     "accuracy_on_stated": {"correct": tp, "wrong": fp, "missed": fn}, "users": out})
    print(f"done -> {OUT}  correct={tp} wrong={fp} missed={fn}")


if __name__ == "__main__":
    main()
