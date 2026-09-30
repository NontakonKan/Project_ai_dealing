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
        """GRAPH_BACKEND=neo4j (ค่าเริ่มต้น): อ่านกราฟจาก Neo4j ด้วย Cypher ทุกคำขอ (graph/neo4j_view.py)
        GRAPH_BACKEND=memory: สร้างกราฟในหน่วยความจำจากไฟล์ใน data/ (ใช้ทดลอง/ประเมินผลโดยไม่เปิด Neo4j)
        Neo4j ต่อไม่ได้ -> ใช้กราฟในหน่วยความจำแทนอัตโนมัติ (บอทยังตอบได้) พร้อมแจ้งเตือน"""
        import logging
        import os
        log = logging.getLogger("graph")
        if os.getenv("GRAPH_BACKEND", "neo4j").lower() == "neo4j":
            try:
                from graph.neo4j_view import Neo4jGraphView
                view = Neo4jGraphView.connect()
                self._warn_if_stale(view, log)
                self.graph_backend = "neo4j"
                return view
            except Exception as e:
                log.warning("ต่อ Neo4j ไม่ได้ (%s) -> ใช้กราฟในหน่วยความจำ", type(e).__name__)
        self.graph_backend = "memory"
        return GraphView.load()

    @staticmethod
    def _warn_if_stale(view, log):
        """chunk ใน Neo4j ต้องตรงกับคลังความรู้ที่ใช้ค้น (ChromaDB) — ไม่ตรง = ลืม import หลังสกัดใหม่"""
        from ..common.io_utils import read_jsonl
        from ..common.paths import PROCESSED
        local = {c["chunk_id"] for c in read_jsonl(PROCESSED / "book_chunks.jsonl")}
        remote = {r["id"] for r in view._read("MATCH (n:BookChunk {dataset:$dataset, snapshot:$snapshot}) RETURN n.id AS id")}
        if local != remote:
            log.warning("Neo4j ไม่ตรงกับคลังความรู้ (chunk ในเครื่อง %d / ใน Neo4j %d) -> รัน python -m graph.import_neo4j",
                        len(local), len(remote))

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

    def faculty_sim(self, a, b) -> float:
        """คณะที่อยากได้ตรงกับคณะของอีกฝ่าย (เฉลี่ยเฉพาะทิศที่มีคนระบุคณะที่อยากได้) — คะแนนบวก ไม่ตัดใครทิ้ง"""
        from ..profile.faculty import normalize

        def one(x, y):
            wants = self.users[x]["preferences"].get("faculty_wants") or []
            if not wants:
                return None
            fac = self.users[y]["demographic"].get("faculty") or ""
            return 1.0 if (normalize(fac) or fac) in wants else 0.0
        sims = [s for s in (one(a, b), one(b, a)) if s is not None]
        return sum(sims) / len(sims) if sims else 0.0

    def candidates(self, user_id) -> list:
        """hard filter เดียวกับ Dense ของฟาริก: ยินยอมทั้งคู่ / เพศตรงกันสองทาง / ไม่เคย unmatch-pass กัน"""
        me = self.users[user_id]
        blocked = {e["about_user"] if e["from_user"] == user_id else e["from_user"]
                   for e in self.events if e["type"] in ("unmatch", "pass") and user_id in (e["from_user"], e["about_user"])}
        return [cid for cid, c in self.users.items() if cid not in blocked and eligible(me, c, ())]
