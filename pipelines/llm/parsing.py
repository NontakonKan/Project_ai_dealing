"""แปลง output ของ LLM -> ข้อมูลที่เชื่อถือได้

ด่านกันมั่ว (ใช้กับทุก format):
  1. parse JSON (รองรับ ```json ... ``` / มีข้อความปน)
  2. id ต้องอยู่ใน taxonomy ของ field นั้น
  3. evidence ต้องปรากฏในข้อความต้นฉบับจริง (กันโมเดลแต่งข้อมูลที่ผู้ใช้ไม่ได้พูด)
"""
import json
import re
from collections import Counter

RE_JSON = re.compile(r"\{.*\}", re.S)
RE_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")   # [3] และ [1, 5]


def parse_json(text: str):
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    for candidate in (text, *(m.group(0) for m in RE_JSON.finditer(text))):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


RE_ITEM = re.compile(r'\{[^{}]*?"id"\s*:\s*"[^"]+"[^{}]*\}')
RE_FIELD = re.compile(r'"(\w+)"\s*:\s*\[')


def parse_partial(text: str, fields):
    """JSON ที่ถูกตัดกลางคัน (โมเดลเขียนเกิน num_predict) -> เก็บเฉพาะรายการที่ปิดวงเล็บครบ

    วัดจริง: ข้อความยาว ("ผมชอบหมา รักสัตว์ เวลาว่างชอบเล่นดนตรี ...") โมเดลเขียนรายการขยะซ้ำจนเกิน 384 token
    -> parse_json ล้ม -> ทิ้งทุกรายการ รวม hobby:pets ที่ถูกต้อง; รายการที่กู้ได้ยังต้องผ่าน validate ทุกด่านเหมือนเดิม
    """
    marks = [(m.group(1), m.end()) for m in RE_FIELD.finditer(text or "") if m.group(1) in fields]
    if not marks:
        return None
    out = {}
    for i, (f, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        items = []
        for m in RE_ITEM.finditer(text[start:end]):
            try:
                items.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                continue
        out.setdefault(f, []).extend(items)
    return out


def _norm(s):
    return re.sub(r"\s+", "", s or "").lower()


RE_EV_SPLIT = re.compile(r"\s*[,，、/]\s*")


def _found(evidence, src):
    """evidence ต้องมีในข้อความจริง — โมเดลมักเขียนหลายท่อนคั่นด้วยจุลภาค ("ชอบสังสรรค์กับเพื่อน, ไปคอน")
    ทั้งก้อนไม่มีในแชท แต่ทุกท่อนมี -> นับว่ามีหลักฐาน (ทุกท่อนต้องมีจริง ไม่ใช่แค่บางท่อน)"""
    whole = _norm(evidence)
    if whole in src:
        return True
    parts = [_norm(x) for x in RE_EV_SPLIT.split(evidence or "") if _norm(x)]
    return len(parts) > 1 and all(x in src for x in parts)


def validate(obj, source_text, allowed: dict, require_evidence=True):
    """คืน (clean: {field: [item]}, stats) — item ที่ไม่ผ่านถูกทิ้งและนับใน stats"""
    stats = Counter()
    clean = {f: [] for f in allowed}
    if obj is None:
        stats["json_error"] += 1
        return clean, stats
    src = _norm(source_text)
    for f, ids in allowed.items():
        seen = set()
        for it in obj.get(f) or []:
            if isinstance(it, str):
                it = {"id": it, "evidence": ""}
            if not isinstance(it, dict) or it.get("id") not in ids:
                stats["invalid_id"] += 1
                continue
            ev = _norm(it.get("evidence"))
            if require_evidence and (not ev or not _found(it.get("evidence"), src)):
                stats["no_evidence"] += 1
                continue
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            clean[f].append(it)
            stats["kept"] += 1
    return clean, stats


def citations(answer: str, n_refs: int) -> dict:
    cited = [int(n) for grp in RE_CITE.findall(answer) for n in grp.split(",")]
    return {"cited": sorted(set(cited)), "n_cited": len(set(cited)),
            "invalid": sorted({c for c in cited if not 1 <= c <= n_refs}),
            "abstained": "ไม่มีข้อมูลเพียงพอ" in answer}
