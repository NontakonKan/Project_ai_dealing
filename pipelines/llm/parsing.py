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


def _norm(s):
    return re.sub(r"\s+", "", s or "").lower()


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
            if require_evidence and (not ev or ev not in src):
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
