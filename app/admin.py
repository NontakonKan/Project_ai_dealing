"""ดูข้อมูลผู้ใช้จริงในระบบ (รันอีกหน้าต่างได้ ไม่ต้องหยุด bot)

  python -m app.admin users          # รายชื่อผู้ใช้ LINE ทั้งหมด
  python -m app.admin user L0002     # รายละเอียด + ข้อความล่าสุดของคนนั้น
  python -m app.admin stats          # สรุปการใช้งาน (เจตนา, การ์ด, คำขอทำความรู้จัก)
  python -m app.admin tail           # ดูข้อความใหม่แบบ realtime (Ctrl+C ออก)
ใช้ฐานข้อมูลเดียวกับ bot (data/app/psu_dealing.db) / --sim = ดูของ simulator
"""
import sys
import time
from datetime import datetime

if "--sim" in sys.argv:
    import os
    from pipelines.common.paths import DATA
    os.environ["APP_DB"] = str(DATA / "app" / "simulate.db")

from . import storage  # noqa: E402
from .profile import build_summaries, describe  # noqa: E402

fmt_t = lambda ts: datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else "-"


def users():
    with storage.db() as c:
        rows = c.execute("""SELECT u.user_id, u.display_name, u.state, u.created_at,
                                   (SELECT COUNT(*) FROM messages m WHERE m.user_id=u.user_id AND m.role='user') AS n_msg,
                                   (SELECT MAX(ts) FROM messages m WHERE m.user_id=u.user_id) AS last
                            FROM line_users u ORDER BY u.created_at""").fetchall()
    print(f"{'ID':<7}{'ชื่อ':<16}{'สถานะ':<22}{'ยินยอม':<8}{'ข้อความ':<9}{'สมัคร':<13}ใช้ล่าสุด")
    for r in rows:
        p = storage.load_profile(r["user_id"]) or {}
        consent = "✅" if p.get("consent", {}).get("matching") else "—"
        print(f"{r['user_id']:<7}{(r['display_name'] or '')[:14]:<16}{r['state']:<22}{consent:<8}{r['n_msg']:<9}"
              f"{fmt_t(r['created_at']):<13}{fmt_t(r['last'])}")
    print(f"\nรวม {len(rows)} คน")


def user(uid):
    p = storage.load_profile(uid)
    if not p:
        return print("ไม่พบผู้ใช้", uid)
    d = p["demographic"]
    print(f"{uid} {p.get('display_name', '')} │ {d.get('gender')}→{d.get('seeking')} อายุ {d.get('age')} {d.get('faculty')}")
    print(describe(build_summaries(p)))
    print("\n— ข้อความล่าสุด —")
    for m in storage.recent_messages(uid, 20):
        print(("👤 " if m["role"] == "user" else "🤖 ") + m["text"][:150].replace("\n", " "))


def stats():
    with storage.db() as c:
        q = lambda sql: c.execute(sql).fetchall()
        print("ข้อความตามเจตนา:", dict(q("SELECT intent, COUNT(*) FROM messages WHERE role='user' GROUP BY intent")))
        print("การ์ดแนะนำคู่ที่ส่ง:", q("SELECT COUNT(*) FROM suggestions")[0][0])
        print("events:", dict(q("SELECT type, COUNT(*) FROM events GROUP BY type")))
        print("คำขอทำความรู้จัก:", dict(q("SELECT status, COUNT(*) FROM intros GROUP BY status")))
        print("ผู้ใช้ที่ส่ง LINE ID แล้ว:", q("SELECT COUNT(*) FROM contacts")[0][0])


def tail():
    print("ดูข้อความใหม่ (Ctrl+C เพื่อออก)")
    with storage.db() as c:
        last = c.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    try:
        while True:
            with storage.db() as c:
                rows = c.execute("SELECT * FROM messages WHERE id>? ORDER BY id", (last,)).fetchall()
            for r in rows:
                last = r["id"]
                who = "👤" if r["role"] == "user" else "🤖"
                print(f"{fmt_t(r['ts'])} {r['user_id']} {who} [{r['intent']}] {r['text'][:120].replace(chr(10), ' ')}")
            time.sleep(2)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sim"]
    cmd = args[0] if args else "users"
    {"users": users, "stats": stats, "tail": tail}.get(cmd, lambda: user(args[1]) if len(args) > 1 else print(__doc__))() \
        if cmd != "user" else user(args[1])
