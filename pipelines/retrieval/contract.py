"""สัญญากลางระหว่าง Retrieval (ส่วน 2/3/4) กับ LLM (ส่วน 5/6)

ทุก retriever ต้องมีเมธอด retrieve(query, k) -> RetrievalResult
LLM layer ไม่สนว่า context มาจาก Dense, Graph หรือ Hybrid -> เปลี่ยน retriever ได้โดยไม่แก้ฝั่ง LLM
"""
from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol

Kind = Literal["chunk", "candidate", "graph_fact"]
Mode = Literal["dense", "graph", "hybrid"]


@dataclass
class RetrievalItem:
    id: str                 # chunk_id / user_id / "rule:attach:anxious-attach:avoidant"
    kind: Kind              # chunk = ความรู้จากหนังสือ, candidate = โปรไฟล์คู่, graph_fact = ความสัมพันธ์ใน Graph
    text: str               # ข้อความที่จะใส่ใน prompt (ต้องอ่านรู้เรื่องโดยไม่ต้องมี metadata)
    score: float            # ยิ่งมากยิ่งเกี่ยวข้อง (ไม่ต้อง normalize ข้าม retriever)
    source: Mode            # retriever ที่หาเจอ
    meta: dict = field(default_factory=dict)  # เช่น concepts, section_title, path


@dataclass
class RetrievalResult:
    mode: Mode
    query: str
    items: list
    latency_ms: float = 0.0

    def to_dict(self):
        return asdict(self)


class Retriever(Protocol):
    mode: Mode

    def retrieve(self, query: str, k: int = 8) -> RetrievalResult: ...
