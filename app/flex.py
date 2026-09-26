"""ข้อความ LINE: text + quick reply + Flex การ์ดแนะนำคู่ (ตามซีน 3 ใน req.md)"""

MENU = [("💞 หาคู่ให้หน่อย", "หาคู่ให้หน่อย"), ("💬 ปรึกษาเรื่องความรัก", "อยากปรึกษาเรื่องความรักหน่อย"),
        ("📋 โปรไฟล์ของฉัน", "โปรไฟล์ของฉัน")]


def text(msg, quick=None):
    m = {"type": "text", "text": msg[:4900]}
    if quick:
        m["quickReply"] = {"items": [{"type": "action", "action": {"type": "message", "label": lab[:20], "text": t}}
                                     for lab, t in quick][:13]}
    return m


def postback_quick(msg, options):
    """options = [(label, data)] -> ปุ่ม postback (เช่น ยินยอม/ไม่ยินยอม)"""
    return {"type": "text", "text": msg, "quickReply": {"items": [
        {"type": "action", "action": {"type": "postback", "label": lab[:20], "data": data, "displayText": lab}}
        for lab, data in options]}}


def _profile_body(person, header, score_pct, reasons, reasons_title, tip=None):
    from pipelines.common import taxonomy
    lab = taxonomy.labels()
    d, p = person["demographic"], person["persona"]
    title = f"{person.get('display_name') or 'ผู้ใช้'} ({d.get('age') or '-'} ปี)"
    traits = ", ".join(lab[x["id"]] for x in p.get("traits", [])[:2])
    hobbies = ", ".join(lab[x["id"]] for x in p.get("hobbies", [])[:3])
    sub = "\n".join(x for x in (d.get("faculty") and f"🎓 คณะ{d['faculty']}", traits and f"🙂 {traits}",
                                  hobbies and f"🎧 ชอบ{hobbies}") if x)
    body = [{"type": "text", "text": header, "size": "sm", "color": "#8a5cf6", "weight": "bold", "wrap": True},
            {"type": "text", "text": title, "size": "xl", "weight": "bold", "wrap": True},
            {"type": "text", "text": sub or "-", "size": "xs", "color": "#6b7280", "wrap": True}]
    if score_pct:
        body.append({"type": "text", "text": f"ความเข้ากันได้ {score_pct}%", "size": "md", "color": "#16a34a",
                     "weight": "bold", "margin": "md"})
    body += [{"type": "separator", "margin": "md"},
             {"type": "text", "text": reasons_title, "weight": "bold", "size": "sm", "margin": "md"},
             *[{"type": "text", "text": f"• {r}", "size": "sm", "wrap": True} for r in reasons[:4]]]
    if tip:
        body += [{"type": "text", "text": "📖 เคล็ดลับเริ่มคุย", "weight": "bold", "size": "sm", "margin": "md"},
                 {"type": "text", "text": tip[:400], "size": "sm", "wrap": True}]
    return title, body


def _bubble(alt, body, buttons):
    return {"type": "flex", "altText": alt[:390],
            "contents": {"type": "bubble", "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body},
                         "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                             {"type": "button", "style": style, "height": "sm",
                              "action": {"type": "postback", "label": lab, "data": data, "displayText": lab}}
                             for lab, data, style in buttons]}}}


def match_card(candidate, score_pct, reasons, tip):
    """การ์ดแนะนำคู่ (ซีน 3) — ยังไม่มีช่องทางติดต่อ จนกว่าอีกฝ่ายจะยินยอม"""
    title, body = _profile_body(candidate, "🎯 เราพบคู่ที่น่าจะเข้ากับคุณ", score_pct, reasons, "💡 ทำไมระบบถึงแนะนำคู่นี้", tip)
    cid = candidate["user_id"]
    return _bubble(f"แนะนำคู่: {title}", body, [
        ("สนใจทำความรู้จัก", f"action=intro&target={cid}", "primary"),
        ("ขอผ่านก่อน", f"action=pass&target={cid}", "secondary"),
        ("เลิกคุยกับคนนี้", f"action=unmatch&target={cid}", "link")])


def request_card(requester, intro_id, score_pct, reasons):
    """การ์ดที่ส่งให้อีกฝ่ายประเมิน: ยินยอมให้ทำความรู้จักไหม (ยังไม่เปิดเผยช่องทางติดต่อของใคร)"""
    title, body = _profile_body(requester, "💌 มีคนสนใจอยากทำความรู้จักคุณ", score_pct, reasons, "💡 จุดที่เข้ากับคุณ")
    body.append({"type": "text", "text": "ถ้ายินยอม ทั้งสองฝ่ายจะได้ LINE ID ของกันและกัน / ถ้าไม่สะดวก อีกฝ่ายจะไม่ได้ข้อมูลใดๆ ของคุณ",
                 "size": "xxs", "color": "#6b7280", "wrap": True, "margin": "md"})
    return _bubble(f"มีคนสนใจทำความรู้จักคุณ: {title}", body, [
        ("ยินยอมให้ทำความรู้จัก", f"action=accept&req={intro_id}", "primary"),
        ("ไม่สะดวก", f"action=decline&req={intro_id}", "secondary")])


def to_plain(msg) -> str:
    """แสดงผลข้อความ LINE เป็นตัวอักษร (ใช้ใน simulator)"""
    if msg["type"] == "text":
        q = msg.get("quickReply", {}).get("items", [])
        return msg["text"] + (("\n   [ปุ่ม] " + " | ".join(i["action"]["label"] for i in q)) if q else "")
    body = msg["contents"]["body"]["contents"]
    btns = msg["contents"]["footer"]["contents"]
    lines = [c["text"] for c in body if c["type"] == "text"]
    return "┌─ FLEX ─────\n│ " + "\n│ ".join(lines) + "\n└ [ปุ่ม] " + " | ".join(b["action"]["label"] for b in btns)
