"""เอาผู้ใช้จริงจาก LINE เข้า pool เดียวกับผู้ใช้จำลอง (Dense + Graph + Hybrid ทำงานเหมือนเดิม)

- Graph: build_graph ของผู้ใช้คนนั้นคนเดียว แล้ว GraphView.add() (ไม่ build ทั้งกราฟใหม่)
- Dense: encode persona/preference ของผู้ใช้จริงด้วย bge-m3 ตัวเดียวกับ index แล้วคำนวณสองทางกับ vector ใน ChromaDB
         เติมผลลง ctx.dense_cache -> matcher ใช้ต่อได้เลย
- ค่านิยม: ใส่ลง ctx.values_struct
- red flag ที่ผู้ใช้จริงรายงานผู้ใช้จำลอง: เก็บใน SQLite แล้วรวมตอนโหลด
"""
import threading

from graph.build import build_graph
from pipelines.common import taxonomy
from pipelines.feedback.policy import REPORT_THRESHOLD
from pipelines.hybrid.config import HybridConfig
from pipelines.hybrid.context import HybridContext

from . import storage

_lock = threading.Lock()
_ctx = None


def ctx() -> HybridContext:
    global _ctx
    with _lock:
        if _ctx is None:
            _ctx = HybridContext()
            _ctx.events = _ctx.events + storage.all_events()
            for r in storage.reports():
                u = _ctx.users.get(r["target_id"])
                if u:
                    _apply_report(u, r["rf_id"], r["count"])
            for p in storage.all_profiles():
                register(p)
    return _ctx


def _apply_report(user, rf_id, count):
    cur = next((x for x in user["reported_traits"] if x["id"] == rf_id), None)
    if cur:
        cur["report_count"] += count
    else:
        user["reported_traits"].append({"id": rf_id, "report_count": count})
    for x in user["reported_traits"]:
        x["usable"] = x["report_count"] >= REPORT_THRESHOLD


def register(profile):
    """เพิ่ม/อัปเดตผู้ใช้จริงใน context (เรียกทุกครั้งที่โปรไฟล์เปลี่ยน)"""
    c = _ctx
    if c is None:
        return
    c.users[profile["user_id"]] = profile
    if profile["demographic"].get("gender") and profile["consent"].get("matching"):
        sub, _ = build_graph(taxonomy.load(), [_graph_ready(profile)], [], [])
        c.graph.add(sub)
    v = profile.get("values", {})
    c.values_struct[profile["user_id"]] = {"self": v.get("self", {}), "wants": v.get("wants", {})}
    for key in [k for k in c.dense_cache if k[0] == profile["user_id"]]:
        del c.dense_cache[key]


def _graph_ready(profile):
    """build_graph ต้องการ field ครบแบบ mock"""
    d = profile["demographic"]
    return {**profile, "demographic": {**d, "age": d.get("age") or 0, "gender": d.get("gender") or "NB"},
            "persona": {**profile["persona"], "attachment_style": profile["persona"].get("attachment_style") or None}}


def dense_for_live(user_id, cfg=HybridConfig()):
    """คะแนน Dense สองทาง (harmonic mean) ระหว่างผู้ใช้จริงกับผู้สมัครทุกคนใน index"""
    from pipelines.dense.embedding import encode
    c = ctx()
    key = (user_id, cfg.lambda_neg)
    if key in c.dense_cache:
        return c.dense_cache[key]
    s = c.users[user_id]["summaries"]
    persona_v, pref_v = encode([s.get("persona_text") or "-", s.get("preference_text") or "-"])
    idx, out = c.dense, {}
    for cid, i in idx.positions["persona"].items():
        if cid not in idx.positions["preference"]:
            continue
        fwd = max(0.0, float(pref_v @ idx.vectors["persona"][i]))
        rev = max(0.0, float(idx.vectors["preference"][idx.positions["preference"][cid]] @ persona_v))
        score = 2 * fwd * rev / (fwd + rev) if fwd + rev else 0.0
        out[cid] = {"user_id": cid, "score": score, "forward": fwd, "reverse": rev}
    others = [u for uid, u in c.users.items() if u.get("source") == "line" and uid != user_id and u.get("summaries")]
    if others:   # ผู้ใช้จริงคนอื่นไม่อยู่ใน ChromaDB -> encode สด (จำนวนน้อย)
        vecs = encode([t for u in others for t in (u["summaries"].get("persona_text") or "-", u["summaries"].get("preference_text") or "-")])
        for i, u in enumerate(others):
            op, oq = vecs[2 * i], vecs[2 * i + 1]
            fwd, rev = max(0.0, float(pref_v @ op)), max(0.0, float(oq @ persona_v))
            out[u["user_id"]] = {"user_id": u["user_id"], "score": 2 * fwd * rev / (fwd + rev) if fwd + rev else 0.0,
                                 "forward": fwd, "reverse": rev}
    c.dense_cache[key] = out
    return out


def add_event(event):
    storage.add_event(event)
    ctx().events.append(event)


def add_report(target_id, rf_id):
    """รายงาน red flag ถึงผู้ใช้จำลอง/ผู้ใช้จริง -> นับรวม (ใช้ได้เมื่อ >= 3 คน)"""
    storage.add_report(target_id, rf_id)
    u = ctx().users.get(target_id)
    if u:
        _apply_report(u, rf_id, 1)
