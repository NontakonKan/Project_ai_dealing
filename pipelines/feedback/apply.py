"""นำผลที่ route แล้วไปอัปเดตโปรไฟล์ (ใช้ทั้งกับ mock และข้อมูลจริงจาก LINE)"""
from .policy import REPORT_THRESHOLD


def _accumulate(items: list, new_id: str, severity: float, source: str):
    cur = next((v for v in items if v["id"] == new_id), None)
    if cur:
        cur["weight"] = round(1 - (1 - cur["weight"]) * (1 - severity), 3)   # noisy-OR สะสม
        cur["count"] = cur.get("count", 1) + 1
        cur["source"] = source
    else:
        items.append({"id": new_id, "weight": severity, "source": source, "count": 1})


def apply_unmatch(speaker: dict, target: dict, routed: dict, event_id: str) -> None:
    src = f"breakup:{event_id}"
    for x in routed["speaker_avoids"]:
        _accumulate(speaker["preferences"]["avoids"], x["id"], x["severity"], src)
    for x in routed["speaker_wants"]:
        _accumulate(speaker["preferences"]["wants"], x["id"], x["severity"], src)
    for x in routed["report_target"]:
        rep = next((v for v in target["reported_traits"] if v["id"] == x["id"]), None)
        if rep:
            rep["report_count"] += 1
        else:
            target["reported_traits"].append({"id": x["id"], "report_count": 1})
    for r in target["reported_traits"]:
        r["usable"] = r["report_count"] >= REPORT_THRESHOLD
