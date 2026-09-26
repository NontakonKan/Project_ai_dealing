"""ชุดทดสอบ (ทุกชุดมีเฉลย) — มาจาก mock data ของส่วน 1"""
from ...common.io_utils import read_json, read_jsonl
from ...common.paths import DATA, MOCK


def extraction(limit=None):
    """แชทจำลอง + gold: hobbies / traits / wants"""
    rows = [{"id": c["chat_id"], "input": c["text"], "gold": c["gold"]} for c in read_jsonl(MOCK / "chats.jsonl")]
    return rows[:limit]


def unmatch(limit=None):
    rows = [{"id": e["event_id"], "input": e["raw_reason"],
             "gold": {f: [x["id"] for x in e["gold_extracted"].get(f, [])] for f in ("red_flags", "appearance", "hygiene")}}
            for e in read_jsonl(MOCK / "events.jsonl") if e["type"] == "unmatch"]
    return rows[:limit]


def rag(limit=None):
    return read_json(DATA / "eval" / "rag_questions.json")[:limit]


def unmatch_sensitive(limit=None):
    """เหตุผลเลิกคุยที่ปนรูปลักษณ์/สีผิว/กลิ่นตัว — วัด false red flag (รูปลักษณ์ถูกจัดเป็นพฤติกรรม)"""
    return read_json(DATA / "eval" / "unmatch_sensitive.json")[:limit]


def unmatch_heldout(limit=None):
    """สำนวนที่ระบบไม่เคยเห็น (gemma3:12b เขียนจากคำอธิบายภาษาอังกฤษ + ตรวจโดยคน) — ใช้เฉพาะข้อที่ไม่ถูกคัดออก"""
    rows = [r for r in read_json(DATA / "eval" / "unmatch_heldout.json") if r["review"]["status"] != "excluded"]
    return rows[:limit]
