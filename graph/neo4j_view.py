"""กราฟที่อ่านจาก Neo4j ทุกคำขอ (Cypher) — interface เดียวกับ graph.view.GraphView

ใช้แทน GraphView ในบอทได้ทันที (HybridContext.graph เลือกด้วย GRAPH_BACKEND): อัลกอริทึมเดิม
(graph/retrieve.py, graph/scorer.py) เรียก g.rel / g.about / g.rules / g.nodes ... แล้วคลาสนี้แปลงเป็น Cypher

- ลำดับ: เส้นเรียงตาม r.id เหมือนกราฟในหน่วยความจำ (เหตุผลบนการ์ดคู่เรียงเหมือนเดิม)
- อ่าน: เฉพาะ snapshot ที่ active ของ dataset (DealingDataset.active_snapshot) ผ่าน key ที่มี unique constraint
- เร็ว: หาคู่ต้องเรียก rel() หลายพันครั้ง -> prefetch() ดึงเส้นขาออกของทุกคนที่เกี่ยวข้องใน Cypher เดียวต่อคำขอ
  ผลที่ดึงมาเก็บไว้ไม่เกิน CACHE_TTL วินาที (ภายในคำขอเดียว) เพื่อไม่ยิงคำถามเดิมซ้ำในคำขอเดียวกัน
- เขียน: ผู้ใช้ LINE (add / remove) ติดป้าย live=true แยกจากข้อมูลที่ import เพื่อให้ import ซ้ำได้
"""
import os
import time

from .schema import DATASET, LABELS, RELATIONS
from .view import RULE_SIGN

CACHE_TTL = 5.0
_EXTRA = ("key", "dataset", "snapshot", "live")      # property ที่ Neo4j เติมเอง ไม่ใช่ข้อมูลกราฟ
_ROLE = {"Concept", "DealingEntity"}


def _clean(props, drop_id=True):
    return {k: v for k, v in dict(props).items() if k not in _EXTRA and not (drop_id and k == "id")}


def _type(rel_type):
    if rel_type not in RELATIONS and rel_type not in RULE_SIGN and rel_type not in ("ABOUT", "NEXT_CHUNK"):
        raise ValueError(f"unknown relationship type: {rel_type}")
    return rel_type


def load_env(path=None):
    """ค่า NEO4J_* อยู่ใน graph/.env (ใช้ร่วมกับ docker compose) — โหลดเฉพาะค่าที่ยังไม่ได้ตั้งใน environment"""
    path = path or os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.startswith("NEO4J_"):
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class _Lookup:
    """mapping แบบ lazy: .get(key) / [key] / in -> Cypher (ใช้แทน dict ของ GraphView)"""

    def __init__(self, view, fetch):
        self.view, self.fetch = view, fetch

    def get(self, key, default=None):
        value = self.view._cached(("lookup", id(self), key), lambda: self.fetch(key))
        return value if value else default

    def __getitem__(self, key):
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __contains__(self, key):
        return self.get(key) is not None


class _Nodes(_Lookup):
    def __init__(self, view):
        super().__init__(view, view._node)

    def items(self):
        return ((n["id"], n) for n in self.view._all_nodes())

    def values(self):
        return (n for n in self.view._all_nodes())


class _Rules:
    """(a, b) -> (rel, weight, reason) ทั้งสองทิศ เหมือน GraphView.rules"""

    def __init__(self, view):
        self.view = view

    def _all(self):
        def fetch():
            rows = self.view._read(
                "MATCH (a:DealingEntity {dataset:$dataset, snapshot:$snapshot})-[r]->"
                "(b:DealingEntity {dataset:$dataset, snapshot:$snapshot}) "
                "WHERE type(r) IN $types RETURN a.id AS a, b.id AS b, type(r) AS t, r.weight AS w, r.reason AS reason "
                "ORDER BY r.id",
                types=list(RULE_SIGN))
            out = {}
            for r in rows:
                out[(r["a"], r["b"])] = out[(r["b"], r["a"])] = (r["t"], r["w"] or 0.0, r["reason"] or "")
            return out
        return self.view._cached(("rules",), fetch)

    def __contains__(self, pair):
        return pair in self._all()

    def __getitem__(self, pair):
        return self._all()[pair]

    def items(self):
        return self._all().items()


class Neo4jGraphView:
    def __init__(self, driver, database="neo4j", dataset=DATASET):
        self.driver, self.database, self.dataset = driver, database, dataset
        self._cache = {}
        row = self._run("MATCH (d:DealingDataset {id:$dataset}) RETURN d.active_snapshot AS s", dataset=dataset)
        if not row or not row[0]["s"]:
            raise RuntimeError("ยังไม่ได้ import กราฟเข้า Neo4j (python -m graph.import_neo4j)")
        self.snapshot = row[0]["s"]
        self.nodes = _Nodes(self)
        self.rules = _Rules(self)
        # ความรู้: BookChunk ─ABOUT→ concept / Claim ─ABOUT|SUBJECT|OBJECT→ concept / chunk ─NEXT_CHUNK→ chunk
        self.about = _Lookup(self, lambda c: [(r["id"], r["count"] or 1) for r in self._incoming(c, "ABOUT", "BookChunk", count=True)])
        self.claims_about = _Lookup(self, lambda c: [r["id"] for r in self._incoming(c, "ABOUT", "Claim")])
        self.claims_subject = _Lookup(self, lambda c: [r["id"] for r in self._incoming(c, "SUBJECT", "Claim")])
        self.claims_object = _Lookup(self, lambda c: [r["id"] for r in self._incoming(c, "OBJECT", "Claim")])
        self.previous_chunks = _Lookup(self, lambda c: [r["id"] for r in self._incoming(c, "NEXT_CHUNK", None)])

    # ---------- สร้างจาก environment ----------
    @classmethod
    def connect(cls):
        from neo4j import GraphDatabase
        load_env()
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            raise RuntimeError("ไม่พบ NEO4J_PASSWORD (graph/.env)")
        # OFF: ความสัมพันธ์บางชนิด (เช่น OBJECT ของ Claim) ยังไม่มีในข้อมูล -> Neo4j เตือนทุก query โดยไม่มีผลต่อคำตอบ
        driver = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                                      auth=(os.environ.get("NEO4J_USERNAME", "neo4j"), password),
                                      notifications_min_severity="OFF")
        driver.verify_connectivity()
        import atexit
        atexit.register(driver.close)
        return cls(driver, os.environ.get("NEO4J_DATABASE", "neo4j"))

    # ---------- Cypher ----------
    def _run(self, query, **params):
        records, _, _ = self.driver.execute_query(query, params, database_=self.database, routing_="r")
        return [r.data() for r in records]

    def _read(self, query, **params):
        return self._run(query, dataset=self.dataset, snapshot=self.snapshot, **params)

    def _key(self, node_id):
        return f"{self.dataset}|{self.snapshot}|{node_id}"

    def _cached(self, key, fetch):
        hit = self._cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        value = fetch()
        self._cache[key] = (now, value)
        return value

    def _incoming(self, target, rel_type, source_label, count=False):
        label = f":{source_label}" if source_label else ""
        return self._read(f"MATCH (s:DealingEntity{label})-[r:{_type(rel_type)}]->(t:DealingEntity {{key:$key}}) "
                          f"RETURN s.id AS id{', r.count AS count' if count else ''} ORDER BY r.id", key=self._key(target))

    @staticmethod
    def _as_node(row):
        label = next((l for l in row["labels"] if l not in _ROLE), "")
        return {"id": row["props"]["id"], "label": label, "properties": _clean(row["props"])}

    def _node(self, node_id):
        rows = self._read("MATCH (n:DealingEntity {key:$key}) RETURN labels(n) AS labels, properties(n) AS props",
                          key=self._key(node_id))
        return self._as_node(rows[0]) if rows else None

    def _all_nodes(self):
        """ทั้ง snapshot ใน Cypher เดียว + เติมแคชรายโหนด (ดัชนีค้นข้อความสร้างจาก chunk ทุกอัน:
        เดิมเรียก prop() ทีละ chunk 1,035 ครั้ง)"""
        rows = self._read("MATCH (n:DealingEntity {dataset:$dataset, snapshot:$snapshot}) "
                          "RETURN labels(n) AS labels, properties(n) AS props")
        nodes, now = [self._as_node(r) for r in rows], time.monotonic()
        for n in nodes:
            self._cache[("lookup", id(self.nodes), n["id"])] = (now, n)
        return nodes

    # ---------- interface เดียวกับ GraphView ----------
    def rel(self, node_id, rel_type) -> dict:
        pre = self._cache.get(("out", node_id))
        if pre and time.monotonic() - pre[0] < CACHE_TTL:
            return pre[1].get(rel_type, {})
        return self._cached(("rel", node_id, rel_type), lambda: {
            r["id"]: _clean(r["props"]) for r in self._read(
                f"MATCH (n:DealingEntity {{key:$key}})-[r:{_type(rel_type)}]->(m:DealingEntity) "
                "RETURN m.id AS id, properties(r) AS props ORDER BY r.id", key=self._key(node_id))})

    def prefetch(self, node_ids):
        """เส้นขาออกทุกชนิดของหลายโหนดใน Cypher เดียว (หาคู่: ผู้ใช้ + ผู้สมัครทั้งหมด)"""
        keys = [self._key(n) for n in node_ids]
        rows = self._read("MATCH (n:DealingEntity)-[r]->(m:DealingEntity) WHERE n.key IN $keys "
                          "RETURN n.id AS n, type(r) AS t, m.id AS m, properties(r) AS props ORDER BY r.id", keys=keys)
        out = {n: {} for n in node_ids}
        for r in rows:
            out[r["n"]].setdefault(r["t"], {})[r["m"]] = _clean(r["props"])
        now = time.monotonic()
        for n, rels in out.items():
            self._cache[("out", n)] = (now, rels)

    def prefetch_nodes(self, node_ids):
        """property ของหลายโหนดใน Cypher เดียว (ค้นความรู้: chunk ที่ได้คะแนนข้อความ ~1,000 อันต่อคำถาม)"""
        keys = [self._key(n) for n in node_ids]
        rows = self._read("MATCH (n:DealingEntity) WHERE n.key IN $keys RETURN labels(n) AS labels, properties(n) AS props",
                          keys=keys)
        now = time.monotonic()
        for r in rows:
            n = self._as_node(r)
            self._cache[("lookup", id(self.nodes), n["id"])] = (now, n)

    def label(self, node_id) -> str:
        n = self.nodes.get(node_id)
        return (n or {}).get("properties", {}).get("label_th", node_id)

    def prop(self, node_id, key, default=None):
        n = self.nodes.get(node_id)
        return (n or {}).get("properties", {}).get(key, default)

    def chunk_text(self, chunk_id) -> str:
        return self.prop(chunk_id, "text", "")

    # ---------- เขียน: ผู้ใช้ LINE ----------
    def add(self, graph: dict):
        """เหมือน GraphView.add: เพิ่ม/แทนผู้ใช้ + เส้นขาออก (ข้ามกฎความเข้ากันและ ABOUT ซึ่งเป็นข้อมูลที่ import)"""
        users = [n for n in graph["nodes"] if n["label"] == "User"]
        uids = {n["id"] for n in users}
        edges = [e for e in graph["relationships"]
                 if e["source"] in uids and e["type"] not in RULE_SIGN and e["type"] != "ABOUT"]
        targets = {e["target"] for e in edges}
        others = [n for n in graph["nodes"] if n["id"] in targets and n["label"] != "User"]

        def write(tx):
            for n in users + others:
                if n["label"] not in LABELS:
                    raise ValueError(f"unknown label: {n['label']}")
                props = {**n["properties"], "id": n["id"], "key": self._key(n["id"]),
                         "dataset": self.dataset, "snapshot": self.snapshot, "live": True}
                if n["label"] == "User":
                    tx.run(f"MERGE (n:DealingEntity {{key:$key}}) SET n:User SET n = $props "
                           "WITH n MATCH (n)-[r]->() DELETE r", key=props["key"], props=props).consume()
                else:   # concept ที่ยังไม่มีใน snapshot: สร้างใหม่เท่านั้น ไม่ทับของที่ import
                    tx.run(f"MERGE (n:DealingEntity {{key:$key}}) ON CREATE SET n:{n['label']}, n = $props",
                           key=props["key"], props=props).consume()
            for e in edges:
                tx.run("MATCH (a:DealingEntity {key:$a}), (b:DealingEntity {key:$b}) "
                       f"MERGE (a)-[r:{_type(e['type'])} {{id:$id}}]->(b) SET r = $props",
                       a=self._key(e["source"]), b=self._key(e["target"]), id=e["id"],
                       props={**e["properties"], "id": e["id"], "dataset": self.dataset,
                              "snapshot": self.snapshot, "live": True}).consume()

        with self.driver.session(database=self.database) as s:
            s.execute_write(write)
        self._cache.clear()

    def remove(self, user_id):
        """ผู้ใช้ลบข้อมูล -> ลบโหนดและเส้นทั้งหมดของเขาออกจาก Neo4j (Neo4j เก็บถาวร ต่างจากกราฟในหน่วยความจำ)"""
        with self.driver.session(database=self.database) as s:
            s.execute_write(lambda tx: tx.run("MATCH (n:DealingEntity:User {key:$key}) DETACH DELETE n",
                                              key=self._key(user_id)).consume())
        self._cache.clear()
