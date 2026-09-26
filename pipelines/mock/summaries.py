"""แปลงโปรไฟล์ JSON -> ข้อความสรุป (สำหรับ embedding) + profile_completeness

⚠️ summaries ไม่มีรูปลักษณ์โดยเจตนา: ถ้าใส่ Dense penalty จะ "เรียนรู้" รูปลักษณ์แบบตรวจสอบไม่ได้
   รูปลักษณ์ใช้ผ่าน Graph (tag ที่เจ้าตัวระบุ) + policy.appearance_score() เท่านั้น
"""
from ..common import taxonomy
from .config import LABEL
from .values import self_text, want_text


def build_summaries(u, rng=None):
    p = u["persona"]
    appearance = taxonomy.appearance_ids()
    no_app = lambda xs: [x for x in xs if x["id"] not in appearance]
    lab = lambda xs: ", ".join(LABEL[x["id"]] for x in xs) or "-"
    sleep = {"early": "นอนเร็วตื่นเช้า", "normal": "นอนเวลาปกติ", "late": "นอนดึก"}.get(p["lifestyle"]["sleep"], "")
    weekend = {"stay_home": "วันหยุดชอบอยู่บ้าน", "go_out": "วันหยุดชอบออกไปเจอเพื่อน", "outdoor": "วันหยุดชอบกิจกรรมกลางแจ้ง",
               "cafe": "วันหยุดชอบนั่งคาเฟ่", "self_improve": "วันหยุดชอบพัฒนาตัวเอง"}.get(p["lifestyle"]["weekend"], "")
    v = u.get("_ground_truth_values")
    said, wants_v = (self_text(v, rng), want_text(v, rng)) if v and rng else ("", "")
    u["summaries"] = {
        "persona_text": (f"อายุ {u['demographic']['age']} ปี คณะ{u['demographic']['faculty']} "
                         f"นิสัย: {lab(p['traits'])} งานอดิเรก: {lab(p['hobbies'])} "
                         f"{sleep} {weekend} การสื่อสาร: {lab(p['comm_style'])} "
                         f"รูปแบบความผูกพัน: {LABEL[p['attachment_style']['id']]} ภาษารัก: {lab(p['love_language'])} {said}").strip(),
        "preference_text": f"อยากได้คนที่ {lab(no_app(u['preferences']['wants']))} {wants_v}".strip(),
        "avoid_text": (f"ไม่ชอบคนที่ {lab(no_app(u['preferences']['avoids']))}" if no_app(u["preferences"]["avoids"]) else ""),
        # facet แยก: ค่านิยมนอก taxonomy (ถ้าปนในข้อความยาว สัญญาณจะเจือจางจนจับไม่ได้)
        "values_text": said,
        "values_want_text": wants_v,
    }
    filled = [bool(p["hobbies"]), bool(p["traits"]), bool(p["comm_style"]), p["attachment_style"]["confidence"] >= 0.5,
              bool(p["love_language"]), bool(u["preferences"]["wants"]), bool(u["preferences"]["avoids"]),
              p["lifestyle"]["sleep"] != "unknown", p["lifestyle"]["weekend"] != "unknown"]
    u["profile_completeness"] = round(sum(filled) / len(filled), 2)
