"""แปลงโปรไฟล์ JSON -> ข้อความสรุป (สำหรับ embedding) + profile_completeness"""
from .config import LABEL


def build_summaries(u):
    p = u["persona"]
    lab = lambda xs: ", ".join(LABEL[x["id"]] for x in xs) or "-"
    sleep = {"early": "นอนเร็วตื่นเช้า", "normal": "นอนเวลาปกติ", "late": "นอนดึก"}[p["lifestyle"]["sleep"]]
    weekend = {"stay_home": "วันหยุดชอบอยู่บ้าน", "go_out": "วันหยุดชอบออกไปเจอเพื่อน", "outdoor": "วันหยุดชอบกิจกรรมกลางแจ้ง",
               "cafe": "วันหยุดชอบนั่งคาเฟ่", "self_improve": "วันหยุดชอบพัฒนาตัวเอง"}[p["lifestyle"]["weekend"]]
    u["summaries"] = {
        "persona_text": (f"อายุ {u['demographic']['age']} ปี คณะ{u['demographic']['faculty']} "
                         f"นิสัย: {lab(p['traits'])} งานอดิเรก: {lab(p['hobbies'])} "
                         f"{sleep} {weekend} การสื่อสาร: {lab(p['comm_style'])} "
                         f"รูปแบบความผูกพัน: {LABEL[p['attachment_style']['id']]} ภาษารัก: {lab(p['love_language'])}"),
        "preference_text": f"อยากได้คนที่ {lab(u['preferences']['wants'])}",
        "avoid_text": (f"ไม่ชอบคนที่ {lab(u['preferences']['avoids'])}" if u["preferences"]["avoids"] else ""),
    }
    filled = [bool(p["hobbies"]), bool(p["traits"]), bool(p["comm_style"]), p["attachment_style"]["confidence"] >= 0.5,
              bool(p["love_language"]), bool(u["preferences"]["wants"]), bool(u["preferences"]["avoids"])]
    u["profile_completeness"] = round(sum(filled) / len(filled), 2)
