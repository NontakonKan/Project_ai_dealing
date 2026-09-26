"""มุมมองกราฟในหน่วยความจำ — สร้างจาก graph.build ตัวเดียวกับที่ import เข้า Neo4j

ใช้ตอนทดลอง/ประเมินผลโดยไม่ต้องเปิด Neo4j — ผลเท่ากับ Cypher ใน queries.py (MATCH_FEATURES) (โครงสร้างเหมือน query `shared` / `rule-paths` / `reports` ใน graph/queries.py)
"""
from collections import defaultdict

from .build import ROOT, build_graph, load_inputs

RULE_SIGN = {"COMPATIBLE_WITH": 1.0, "CONFLICTS_WITH": -1.0, "OPPOSITE_OF": -1.0}


class GraphView:
    def __init__(self, graph: dict):
        self.snapshot = graph["snapshot"]
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.out = defaultdict(lambda: defaultdict(dict))     # out[src][REL][dst] = props
        self.rules = {}                                      # (a, b) -> (rel, weight, reason)
        self.about = defaultdict(list)                       # concept -> [(chunk_id, count)]
        for e in graph["relationships"]:
            p = e["properties"]
            if e["type"] in RULE_SIGN:
                self.rules[(e["source"], e["target"])] = self.rules[(e["target"], e["source"])] = \
                    (e["type"], p.get("weight", 0.0), p.get("reason", ""))
            elif e["type"] == "ABOUT":
                self.about[e["target"]].append((e["source"], p.get("count", 1)))
            else:
                self.out[e["source"]][e["type"]][e["target"]] = p

    def add(self, graph: dict):
        """เพิ่มกราฟย่อย (เช่น ผู้ใช้จริงจาก LINE ที่ build ด้วย build_graph) โดยไม่ต้อง build ทั้งกราฟใหม่"""
        for n in graph["nodes"]:
            self.nodes.setdefault(n["id"], n)
            if n["label"] == "User":
                self.nodes[n["id"]] = n
                self.out.pop(n["id"], None)           # ข้อมูลผู้ใช้เปลี่ยน -> ล้างเส้นเดิมของคนนั้น
        for e in graph["relationships"]:
            if e["type"] not in RULE_SIGN and e["type"] != "ABOUT":
                self.out[e["source"]][e["type"]][e["target"]] = e["properties"]

    @classmethod
    def load(cls, data_dir=None):
        inputs, provenance = load_inputs(data_dir or ROOT / "data")
        graph, _ = build_graph(**inputs, provenance=provenance)
        return cls(graph)

    def rel(self, node_id, rel_type) -> dict:
        return self.out[node_id][rel_type]

    def label(self, node_id) -> str:
        return self.nodes.get(node_id, {}).get("properties", {}).get("label_th", node_id)

    def prop(self, node_id, key, default=None):
        return self.nodes.get(node_id, {}).get("properties", {}).get(key, default)

    def chunk_text(self, chunk_id) -> str:
        return self.prop(chunk_id, "text", "")
