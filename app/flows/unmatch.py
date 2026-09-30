"""เลิกคุย (ซีน 2): ถามเหตุผล -> สกัด (พฤติกรรม/รูปลักษณ์/กลิ่นตัว) -> policy -> อัปเดตโปรไฟล์ -> ไม่แนะนำคนนี้อีก"""
from pipelines.common import taxonomy
from pipelines.feedback.apply import apply_unmatch
from pipelines.llm import tasks

from .. import live, storage
from ..flex import postback_quick, text
from . import partners
from .common import event_id, load, save


def ask_reason(line_user, target=None):
    """กดจากการ์ด = รู้เป้าหมาย / พิมพ์เอง = ดูประวัติว่าตอนนี้คุยกับใคร (หลายคน -> ให้เลือก ไม่เดา)"""
    p = load(line_user)
    if not target:
        active = [x for x in partners.history(p["user_id"]) if x["status"] in partners.ACTIVE]
        if not active:
            return [text("ตอนนี้คุณยังไม่ได้คุยกับใครที่ผมแนะนำเลยครับ 🙂", [("หาคู่ให้หน่อย", "หาคู่ให้หน่อย")])]
        talking = [x for x in active if x["status"] in partners.TALKING]
        if len(talking) > 1 or (not talking and len(active) > 1):
            options = (talking or active)[:4]
            return [postback_quick("ตอนนี้คุณคุยอยู่หลายคน จะเลิกคุยกับใครครับ?",
                                   [(partners.name_of(x["user_id"]).split(" · ")[0], f"action=unmatch&target={x['user_id']}")
                                    for x in options])]
        target = (talking or active)[0]["user_id"]
    storage.set_state(line_user["line_user_id"], "await_unmatch_reason", {"target": target})
    return [text(f"เลิกคุยกับ {partners.name_of(target)} นะครับ\n"
                 "เสียใจด้วยนะครับ 🙏 ขอเหตุผลสั้นๆ หน่อยได้ไหมครับ ว่าตรงไหนที่ไม่โอเค "
                 "(อีกฝ่ายจะไม่เห็นสิ่งที่คุณบอกผม) ผมจะใช้หาคนที่เข้ากับคุณมากขึ้น")]


def reason(line_user, msg):
    p, c = load(line_user), live.ctx()
    target = line_user["state_data"].get("target")
    storage.set_state(line_user["line_user_id"], "ready")
    out = tasks.extract_unmatch(msg)
    routed, eid = out["routed"], event_id()
    target_profile = c.users.get(target, {"reported_traits": [], "user_id": target})
    apply_unmatch(p, {"reported_traits": []}, routed, eid)   # อัปเดตฝั่งผู้พูด
    for x in routed["report_target"]:                        # อีกฝ่าย: นับรายงานเฉพาะพฤติกรรม (policy)
        live.add_report(target, x["id"])
    if target_profile.get("source") == "line":
        save(c.users[target])
    save(p)
    live.add_event({"event_id": eid, "type": "unmatch", "from_user": p["user_id"], "about_user": target,
                    "extracted_ids": {k: [x["id"] for x in v] for k, v in out["extracted"].items()}})
    from .. import log
    log.note(f"เลิกคุย {target}: รายงาน={[x['id'] for x in routed['report_target']]} "
             f"สเปกผู้พูด={[x['id'] for x in routed['speaker_avoids'] + routed['speaker_wants']]}")
    labels = taxonomy.labels()
    behaviors = [labels[x["id"]] for x in routed["report_target"]]
    lines = ["รับทราบครับ ระบบจะไม่แนะนำคนนี้ให้อีกนะครับ 🙏"]
    if behaviors:
        lines.append("ผมบันทึกไว้ว่าคุณไม่สบายใจกับ: " + ", ".join(behaviors))
        lines.append("ครั้งต่อไปจะลดน้ำหนักและคัดกรองคนที่มีพฤติกรรมแบบนี้ออกไปให้ครับ")
    elif routed["speaker_avoids"] or routed["speaker_wants"]:
        lines.append("ผมจดสเปกของคุณเพิ่มไว้แล้ว จะใช้หาคนที่ตรงใจมากขึ้นครับ")
    lines.append("มีอะไรอยากระบายเพิ่มไหมครับ?")
    return [text("\n".join(lines), [("หาคนใหม่", "หาคู่ให้หน่อย")])]
