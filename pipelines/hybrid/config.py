"""ค่าตั้งของ Hybrid — ทุกค่าเป็นพารามิเตอร์ทดลองใน evaluate.py"""
from dataclasses import dataclass, replace

from ..common import taxonomy



@dataclass(frozen=True)
class HybridConfig:
    fusion: str = "rrf"          # rrf | weighted
    alpha: float = 0.5           # weighted: น้ำหนัก Dense (1-alpha = Graph)
    rrf_k: int = 60
    hard_redflag: bool = True    # ตัดผู้สมัครที่ถูกรายงาน (>=3) ด้วย red flag ที่ผู้ใช้หลีกเลี่ยง
    lambda_rf: float = 0.3       # ถ้าไม่ตัด: หักคะแนนตามน้ำหนัก avoids
    lambda_neg: float = 0.15     # Dense negative-example penalty (ของฟาริก)
    w_appearance: float = None   # None = ใช้ค่าใน taxonomy.appearance_policy
    w_values: float = 0.0        # facet ค่านิยมนอก taxonomy (bi-encoder บน values_text / values_want_text)
    w_values_struct: float = 0.0  # ค่านิยมที่ LLM อ่านเป็นโครงสร้าง (data/processed/values_structured.json)
    rerank_top: int = 0          # >0 = rerank ผู้สมัคร top-N ด้วย cross-encoder
    rerank_beta: float = 0.5     # น้ำหนักคะแนน reranker ตอนผสมกับคะแนนเดิม

    def with_(self, **kw):
        return replace(self, **kw)

    @property
    def appearance_weight(self):
        return taxonomy.appearance_policy()["w_appearance"] if self.w_appearance is None else self.w_appearance
