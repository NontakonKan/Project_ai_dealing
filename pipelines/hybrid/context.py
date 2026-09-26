"""โหลดทรัพยากรครั้งเดียว (users, events, Dense index, GraphView) + hard filter กลางที่ทุกโหมดใช้ร่วมกัน"""
from functools import cached_property

from ..dense.matching import eligible, load_matching_data
from graph.view import GraphView


class HybridContext:
    def __init__(self, dense_dir=None):
        self.users, self.events = load_matching_data()
        self._dense_dir = dense_dir
        self.dense_cache = {}

    @cached_property
    def dense(self):
        from ..dense.index import DEFAULT_INDEX, DenseIndex   # import ช้า (chromadb) -> โหลดเมื่อใช้
        return DenseIndex(self._dense_dir or DEFAULT_INDEX)

    @cached_property
    def graph(self) -> GraphView:
        return GraphView.load()

    @cached_property
    def values_vectors(self) -> dict:
        """embed facet ค่านิยมแยกจากข้อความยาว (ปนกันแล้วสัญญาณเจือจางจนจับไม่ได้)"""
        from ..dense.embedding import encode
        ids = list(self.users)
        said = encode([self.users[u]["summaries"].get("values_text") or "-" for u in ids])
        want = encode([self.users[u]["summaries"].get("values_want_text") or "-" for u in ids])
        return {u: (said[i], want[i]) for i, u in enumerate(ids)}

    def values_sim(self, a, b) -> float:
        va, vb = self.values_vectors[a], self.values_vectors[b]
        f, r = float(va[1] @ vb[0]), float(vb[1] @ va[0])
        return 2 * f * r / (f + r) if f + r > 0 else 0.0

    @cached_property
    def values_struct(self) -> dict:
        from ..common.io_utils import read_json
        from ..common.paths import PROCESSED
        path = PROCESSED / "values_structured.json"
        return read_json(path)["users"] if path.exists() else {}

    def values_struct_sim(self, a, b) -> float:
        """สัดส่วนค่านิยมที่ A ต้องการและ B บอกว่าเป็น (สองทิศ, ใช้เฉพาะที่ไม่ใช่ unknown)"""
        def one(x, y):
            wants = {d: v for d, v in self.values_struct.get(x, {}).get("wants", {}).items() if v != "unknown"}
            if not wants:
                return 0.0
            has = self.values_struct.get(y, {}).get("self", {})
            return sum(1.0 if has.get(d) == v else -0.5 if has.get(d, "unknown") != "unknown" else 0.0
                       for d, v in wants.items()) / len(wants)
        return (one(a, b) + one(b, a)) / 2

    def candidates(self, user_id) -> list:
        """hard filter เดียวกับ Dense ของฟาริก: ยินยอมทั้งคู่ / เพศตรงกันสองทาง / ไม่เคย unmatch-pass กัน"""
        me = self.users[user_id]
        blocked = {e["about_user"] if e["from_user"] == user_id else e["from_user"]
                   for e in self.events if e["type"] in ("unmatch", "pass") and user_id in (e["from_user"], e["about_user"])}
        return [cid for cid, c in self.users.items() if cid not in blocked and eligible(me, c, ())]
