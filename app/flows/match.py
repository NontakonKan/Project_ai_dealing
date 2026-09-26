"""หาคู่ (ซีน 3): Hybrid จัดอันดับ -> LLM อธิบาย -> Flex การ์ด + ปุ่ม ทำความรู้จัก/ขอผ่าน/เลิกคุย"""
import re

from pipelines.hybrid import matcher
from pipelines.hybrid.config import HybridConfig
from pipelines.hybrid.retrievers import pair_context
from pipelines.llm import tasks

from .. import live, storage
from ..flex import match_card, text
from ..profile import ready_to_match
from .common import event_id, load

# ค่าที่ดีที่สุดจาก data/eval/hybrid (Graph + Dense + ค่านิยมที่ LLM อ่านเป็นโครงสร้าง)
MATCH_CFG = HybridConfig(fusion="weighted", alpha=0.3, w_values_struct=0.3)


def _missing(p):
    d = p["demographic"]
    if not p["consent"]["matching"]:
        return "ต้องยินยอมให้ใช้ข้อมูลเพื่อจับคู่ก่อนนะครับ (พิมพ์ \"ยินยอม\")"
    if not (d.get("gender") and d.get("seeking") and d.get("age")):
        return "ยังขาดข้อมูลพื้นฐาน (เพศ/เพศที่สนใจ/อายุ) ครับ"
    return "ขอรู้จักอีกนิดครับ เล่าเรื่องงานอดิเรก นิสัย หรือสเปกที่ชอบให้ผมฟังหน่อย"


def _clean(t):
    return re.sub(r"\s*[\[(]\d+(?:\s*,\s*\d+)*[\])]", "", t).strip(" :-*#\n")


def _tip(explanation):
    m = re.search(r"เคล็ดลับ[^\n:]*[:\n]?(.*)", explanation, re.S)
    tip = _clean(m.group(1)) if m else ""
    if not tip:   # LLM ไม่ได้ใส่หัวข้อ -> ใช้ย่อหน้าสุดท้าย
        paras = [x for x in explanation.split("\n") if x.strip()]
        tip = _clean(paras[-1]) if paras else ""
    return tip[:350] or "เริ่มจากถามเรื่องงานอดิเรกที่ชอบเหมือนกันก่อนก็ได้ครับ"


def _you(fact):
    """graph_fact เขียนแบบ A/B -> มุมมองผู้ใช้ (คุณ / อีกฝ่าย)"""
    if fact.startswith("A อยากได้คนที่"):
        return fact.replace("A อยากได้คนที่", "คุณอยากได้คนที่").replace("— อีกฝ่ายมีนิสัยนี้", "— อีกฝ่ายมีนิสัยนี้")
    if fact.startswith("B อยากได้คนที่"):
        return fact.replace("B อยากได้คนที่", "อีกฝ่ายอยากได้คนที่").replace("— อีกฝ่ายมีนิสัยนี้", "— ตรงกับนิสัยของคุณ")
    return fact


def find(line_user):
    p = load(line_user)
    if not ready_to_match(p):
        return [text(_missing(p))]
    c = live.ctx()
    live.register(p)
    live.dense_for_live(p["user_id"], MATCH_CFG)
    seen = storage.suggested(p["user_id"])
    ranked = [r for r in matcher.rank(c, p["user_id"], "hybrid", MATCH_CFG, top_k=20) if r["user_id"] not in seen]
    if not ranked:
        return [text("ตอนนี้ยังไม่เจอคนที่เข้ากันเพิ่มครับ 🙏 ลองเล่าเรื่องตัวเองเพิ่มอีกนิด แล้วค่อยให้ผมหาใหม่นะครับ")]
    top = ranked[0]
    cand = c.users[top["user_id"]]
    res = pair_context(c, p["user_id"], cand["user_id"])
    reasons = [_you(it.text) for it in res.items if it.kind == "graph_fact" and not it.text.startswith("⚠️")][:3]
    try:
        explanation = tasks.explain_match(p, cand, res)["explanation"]
    except Exception:
        explanation = "เริ่มจากถามเรื่องงานอดิเรกที่ชอบเหมือนกันก่อนก็ได้ครับ"
    pct = round(100 * min(1.0, (top["graph"] + max(top["dense"], 0.0)) / 1.2))
    storage.add_suggestion(p["user_id"], cand["user_id"], top["score"])
    return [match_card(cand, max(pct, 50), reasons or ["ไลฟ์สไตล์และสเปกใกล้เคียงกัน"], _tip(explanation))]


def pass_(line_user, target):
    p = load(line_user)
    live.add_event({"event_id": event_id(), "type": "pass", "from_user": p["user_id"], "about_user": target})
    return [text("รับทราบครับ 👌 จะไม่แนะนำคนนี้อีก", [("หาคนใหม่", "หาคู่ให้หน่อย")])]
