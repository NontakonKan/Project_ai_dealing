"""จำลอง LINE ในเครื่อง (ไม่ต้องมี token) — ส่ง event รูปแบบเดียวกับ LINE เข้า handlers จริง

  python -m app.simulate            # พิมพ์คุยเอง: กดปุ่มด้วย #1 #2 ... / ออกด้วย /q
  python -m app.simulate --demo     # เดโม 3 ซีนจาก req.md อัตโนมัติ
  python -m app.simulate --mutual   # เดโมทำความรู้จักแบบยินยอมทั้งสองฝ่าย (ผู้ใช้ 3 คน: ยินยอม / ไม่สะดวก)
  python -m app.simulate --reset    # ล้างฐานข้อมูลของ simulator
ใช้ฐานข้อมูลแยก data/app/simulate.db (ไม่ปนกับข้อมูลจริง)
"""
import os
import sys

from pipelines.common.paths import DATA

SIM_DB = DATA / "app" / "simulate.db"
os.environ["APP_DB"] = str(SIM_DB)
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = ""      # บังคับโหมดจำลอง: ไม่ส่งถึง LINE จริง

from . import handlers, line_api  # noqa: E402
from .flex import to_plain  # noqa: E402

USERS = {"A": "Usimulator000000000000000000000001", "B": "Usimulator000000000000000000000002",
         "C": "Usimulator000000000000000000000003"}
NAME = {v: k for k, v in USERS.items()}
USER = USERS["A"]
_buttons = []


def _event(kind, value=None):
    base = {"replyToken": "sim", "source": {"type": "user", "userId": USER}}
    if kind == "follow":
        return {**base, "type": "follow"}
    if kind == "postback":
        return {**base, "type": "postback", "postback": {"data": value}}
    return {**base, "type": "message", "message": {"type": "text", "text": value}}


def send(kind, value=None, show=True):
    global _buttons
    line_api.outbox.clear()
    handlers.handle(_event(kind, value))
    _buttons = []
    others = {}
    for batch in line_api.outbox:
        to = batch.get("to") or USER
        for m in batch["messages"]:
            if to != USER:   # push ไปหาผู้ใช้อื่น (เช่น คำขอทำความรู้จัก)
                others.setdefault(to, []).append(m)
                continue
            if show:
                print("🤖 " + to_plain(m).replace("\n", "\n   "))
            items = m.get("quickReply", {}).get("items", []) if m["type"] == "text" else \
                [{"action": b["action"]} for b in m["contents"]["footer"]["contents"]]
            _buttons += [i["action"] for i in items]
    for to, msgs in others.items():
        pending_push.setdefault(to, []).extend(msgs)
        if show:
            for m in msgs:
                print(f"📨 [ส่งถึงผู้ใช้ {NAME.get(to, to)}] " + to_plain(m).replace("\n", "\n   "))
    if show and _buttons:
        print("   " + "  ".join(f"#{i + 1} {a['label']}" for i, a in enumerate(_buttons)))


pending_push = {}


def as_user(name):
    """สลับไปเป็นผู้ใช้อื่น แล้วแสดงข้อความที่ถูก push มาหาเขา (ปุ่มในข้อความนั้นกดได้)"""
    global USER, _buttons
    USER, _buttons = USERS[name], []
    print(f"\n——— สลับเป็นผู้ใช้ {name} ———")
    for m in pending_push.pop(USER, []):
        items = m.get("quickReply", {}).get("items", []) if m["type"] == "text" else \
            [{"action": b["action"]} for b in m["contents"]["footer"]["contents"]]
        _buttons += [i["action"] for i in items]
    if _buttons:
        print("   " + "  ".join(f"#{i + 1} {a['label']}" for i, a in enumerate(_buttons)))


def press_label(word):
    n = next(i for i, a in enumerate(_buttons, 1) if word in a["label"])
    press(n)


def press(n):
    a = _buttons[n - 1]
    print(f"👤 [กด] {a['label']}")
    if a["type"] == "postback":
        send("postback", a["data"])
    else:
        send("message", a["text"])


def say(msg):
    print(f"\n👤 {msg}")
    send("message", msg)


def demo():
    print("=== เพิ่มเพื่อน OA ===")
    send("follow")
    press(1)                                   # ยินยอม
    for ans in ("ชาย", "หญิง", "22", "วิศวกรรมศาสตร์"):
        say(ans)
    print("\n=== ซีน 1: คุยเล่น + บอกสเปก ===")
    say("วันนี้เหนื่อยมากเลย ทำงานถึงดึกอีกแล้ว ปกติชอบฟังเพลง Lo-Fi ไม่ก็ทำอาหารกินเองเงียบๆ "
        "วันหยุดไม่ค่อยชอบไปที่คนเยอะ ชอบคนใจเย็น คุยด้วยเหตุผล ไม่ขี้เหวี่ยง")
    say("อนาคตอยากมีลูกนะ แล้วก็อยากได้คนที่ชอบเก็บออม วางแผนการเงิน")
    print("\n=== ซีน 3: ขอให้หาคู่ ===")
    say("หาคู่ให้หน่อย")
    print("\n=== ซีน 2: เลิกคุย + บอกเหตุผล ===")
    unmatch_btn = next((i for i, a in enumerate(_buttons, 1) if "เลิกคุย" in a["label"]), None)
    if unmatch_btn:
        press(unmatch_btn)
    say("คนนี้ไม่ไหวว่ะ ติดเพื่อนเกินไป เวลาไม่พอใจชอบหายไปเงียบๆ ไม่อธิบาย ปล่อยให้เดา")
    print("\n=== ปรึกษาเรื่องความรัก ===")
    say("ถ้าแฟนชอบเงียบใส่เวลามีปัญหา ควรทำยังไงดี")
    print("\n=== ดูสิ่งที่ระบบจำได้ + หาคนใหม่ ===")
    say("โปรไฟล์ของฉัน")
    say("หาคู่ให้หน่อย")


def onboard(name, gender, seeking, age, faculty, intro_text):
    as_user(name)
    send("follow", show=False)
    send("postback", "action=consent&v=yes", show=False)
    for ans in (gender, seeking, str(age), faculty):
        send("message", ans, show=False)
    say(intro_text)


def user_id_of(name):
    from . import storage
    return storage.get_line_user(USERS[name])["user_id"]


def mutual():
    print("=== ผู้ใช้จริง 3 คนลงทะเบียน + เล่าเรื่องตัวเอง ===")
    onboard("A", "ชาย", "หญิง", 22, "วิศวกรรมศาสตร์", "ชอบฟังเพลงชิล ทำกับข้าวกินเอง เป็นคนใจเย็น ชอบคนใจดี")
    onboard("B", "หญิง", "ชาย", 21, "วิทยาศาสตร์", "ชอบอ่านหนังสือ ทำขนม เป็นคนใจดี ชอบคนใจเย็น")
    onboard("C", "หญิง", "ชาย", 23, "นิติศาสตร์", "ชอบไปคอนเสิร์ต ปาร์ตี้กับเพื่อน ชอบคนตลก")

    print("\n=== กรณี 1: A สนใจ B → B ยินยอม → แลก LINE ID ===")
    as_user("A")
    print("👤 [กด] สนใจทำความรู้จัก (การ์ดของ B)")
    send("postback", f"action=intro&target={user_id_of('B')}")
    say("nont_a22")                                  # A ส่ง LINE ID (ถูกเก็บไว้ ยังไม่ส่งให้ใคร)
    as_user("B")                                     # B เห็นการ์ดของ A
    press_label("ยินยอม")
    say("praew.b21")                                 # B ส่ง LINE ID -> แลกกันทั้งสองฝ่าย
    as_user("A")
    for m in pending_push.pop(USER, []):
        print("📬 A ได้รับ: " + to_plain(m).replace("\n", "\n   "))

    print("\n=== กรณี 2: A สนใจ C → C ไม่สะดวก → A ไม่ได้ข้อมูลของ C ===")
    as_user("A")
    print("👤 [กด] สนใจทำความรู้จัก (การ์ดของ C)")
    send("postback", f"action=intro&target={user_id_of('C')}")
    as_user("C")
    press_label("ไม่สะดวก")
    as_user("A")
    for m in pending_push.pop(USER, []):
        print("📬 A ได้รับ: " + to_plain(m).replace("\n", "\n   "))


def repl():
    print("พิมพ์ข้อความเพื่อคุยกับบอท | #n = กดปุ่มที่ n | /as B = สลับผู้ใช้ (A/B/C) | /follow = เพิ่มเพื่อนใหม่ | /q = ออก")
    if not SIM_DB.exists():
        send("follow")
    while True:
        try:
            msg = input("\n👤 ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg == "/q":
            break
        if msg.startswith("/as ") and msg[4:].strip().upper() in USERS:
            as_user(msg[4:].strip().upper())
        elif msg == "/follow":
            send("follow")
        elif msg.startswith("#") and msg[1:].isdigit() and 0 < int(msg[1:]) <= len(_buttons):
            press(int(msg[1:]))
        elif msg:
            send("message", msg)


if __name__ == "__main__":
    if "--reset" in sys.argv and SIM_DB.exists():
        SIM_DB.unlink()
        print("ล้างฐานข้อมูล simulator แล้ว")
    if "--mutual" in sys.argv:
        if SIM_DB.exists():
            SIM_DB.unlink()
        mutual()
    elif "--demo" in sys.argv:
        if SIM_DB.exists():
            SIM_DB.unlink()
        demo()
    elif "--reset" not in sys.argv:
        repl()
