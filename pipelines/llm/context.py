"""ประกอบ context จาก RetrievalResult (Dense/Graph/Hybrid) ให้พอดีงบ token ของโมเดล

- dedupe ตาม id (Hybrid อาจได้ chunk ซ้ำจากสองทาง)
- จัดกลุ่มตามชนิด: graph_fact (สั้น แม่น) -> candidate -> chunk
- ตัดเมื่อเกินงบ token และบันทึกว่าตัดทิ้งกี่ชิ้น (ใช้วิเคราะห์ใน benchmark)
"""
from dataclasses import dataclass, field

CHARS_PER_TOKEN = 1.6   # วัดจริง: Typhoon2-8B = 1.64 ตัวอักษรไทย/token (`run calibrate`) ปัดลงเผื่อไว้
KIND_ORDER = ["graph_fact", "candidate", "chunk"]
KIND_TITLE = {"graph_fact": "ความสัมพันธ์จาก Knowledge Graph", "candidate": "ข้อมูลผู้สมัคร",
              "chunk": "ความรู้จากหนังสือ/งานวิจัย"}


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


@dataclass
class ContextPack:
    text: str
    refs: list = field(default_factory=list)       # refs[n-1] = id ของ [n]
    used_tokens: int = 0
    dropped: int = 0
    kinds: dict = field(default_factory=dict)


def build(result, budget_tokens: int) -> ContextPack:
    best = {}
    for it in result.items:
        if it.id not in best or it.score > best[it.id].score:
            best[it.id] = it
    ordered = sorted(best.values(), key=lambda it: (KIND_ORDER.index(it.kind), -it.score))

    pack, sections, used = ContextPack(""), {}, 0
    for it in ordered:
        line = f"[{len(pack.refs) + 1}] {it.text}"
        cost = estimate_tokens(line)
        if used + cost > budget_tokens:
            pack.dropped += 1
            continue
        pack.refs.append(it.id)
        sections.setdefault(it.kind, []).append(line)
        used += cost
    pack.text = "\n\n".join(f"## {KIND_TITLE[k]}\n" + "\n".join(v) for k, v in sections.items())
    pack.used_tokens = used
    pack.kinds = {k: len(v) for k, v in sections.items()}
    return pack
