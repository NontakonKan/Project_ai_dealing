"""Graph placeholder: หา concept ใน query ด้วย taxonomy -> คืนกฎความเข้ากันได้ + chunk ที่ ABOUT concept นั้น
(ส่วน 3 แทนด้วย Cypher บน Neo4j)"""
import time

from ...common import taxonomy
from ...common.io_utils import read_jsonl
from ...common.paths import PROCESSED
from ..contract import RetrievalItem, RetrievalResult

EXTRA_KEYS = {"anxious": "attach:anxious", "avoidant": "attach:avoidant", "secure": "attach:secure",
              "sternberg": "love:intimacy", "สามเหลี่ยม": "love:intimacy"}


def _concepts_in(query):
    q = query.lower()
    labels = taxonomy.labels()
    found = {cid for cid, als in taxonomy.aliases().items() if any(a.lower() in q for a in als if len(a) >= 3)}
    found |= {cid for cid, lab in labels.items() if len(lab) >= 4 and lab in query}
    found |= {cid for key, cid in EXTRA_KEYS.items() if key in q}
    return found


class GraphStub:
    mode = "graph"

    def __init__(self):
        self.chunks = read_jsonl(PROCESSED / "book_chunks.jsonl")
        self.labels = taxonomy.labels()

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        concepts = _concepts_in(query)
        items = []
        for r in taxonomy.rules():
            if r["a"] in concepts or r["b"] in concepts:
                la, lb = self.labels.get(r["a"], r["a"]), self.labels.get(r["b"], r["b"])
                text = f"({la}) -[{r['relation']}]-> ({lb})" + (f": {r['reason']}" if r.get("reason") else "")
                hit = (r["a"] in concepts) + (r["b"] in concepts)
                items.append(RetrievalItem(id=f"rule:{r['a']}-{r['b']}", kind="graph_fact", text=text,
                                           score=round(r["weight"] * hit, 3), source="graph",
                                           meta={"path": [r["a"], r["relation"], r["b"]], "ref": r.get("source")}))
        for c in self.chunks:
            overlap = [x for x in c["concepts"] if x in concepts]
            if overlap:
                score = sum(c["concept_counts"].get(x, 0) for x in overlap) / 10
                items.append(RetrievalItem(id=c["chunk_id"], kind="chunk", text=c["text"], score=round(score, 3),
                                           source="graph", meta={"path": ["BookChunk", "ABOUT", *overlap],
                                                                 "section_title": c["section_title"]}))
        items = sorted(items, key=lambda x: -x.score)[:k]
        return RetrievalResult("graph", query, items, (time.perf_counter() - t0) * 1000)
