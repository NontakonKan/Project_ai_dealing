"""System integration (ไม่ต้องเปิด Ollama/LINE): ลายเซ็น, intent, โปรไฟล์, Flex, onboarding flow

python -m unittest discover -s tests
"""
import base64
import hashlib
import hmac
import os
import tempfile
import unittest

os.environ["APP_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = ""

from app import handlers, intent, line_api, storage  # noqa: E402
from app.flex import match_card, to_plain  # noqa: E402
from app.profile import build_summaries, merge_extraction, new_profile, ready_to_match  # noqa: E402


class SignatureTests(unittest.TestCase):
    def test_valid_and_invalid(self):
        body = b'{"events":[]}'
        sig = base64.b64encode(hmac.new(b"secret", body, hashlib.sha256).digest()).decode()
        self.assertTrue(line_api.verify_signature(body, sig, "secret"))
        self.assertFalse(line_api.verify_signature(body, sig, "other"))
        self.assertFalse(line_api.verify_signature(body, "", "secret"))


class IntentTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(intent.classify("หาคู่ให้หน่อย"), "find_match")
        self.assertEqual(intent.classify("แฟนเงียบใส่ ควรทำยังไง"), "ask_advice")
        self.assertEqual(intent.classify("วันนี้ทำกับข้าวกินเอง"), "chat")
        self.assertEqual(intent.classify("ลบข้อมูลของฉัน"), "delete_me")
        self.assertEqual(intent.classify("ชาย", "onboard_gender"), "onboarding")
        self.assertEqual(intent.classify("ติดเพื่อน", "await_unmatch_reason"), "unmatch_reason")


class ProfileTests(unittest.TestCase):
    def test_merge_no_growth_and_sensitive_pending(self):
        p = new_profile("L9", "x")
        ex = {"hobbies": [{"id": "hobby:cooking"}], "self_described": [{"id": "skin:tan"}, {"id": "body:slim"}]}
        merge_extraction(p, ex)
        merge_extraction(p, ex)
        self.assertEqual(len(p["persona"]["hobbies"]), 1)
        self.assertEqual(p["persona"]["hobbies"][0]["evidence_count"], 2)
        self.assertEqual(p["appearance"]["pending_consent"], ["skin:tan"])   # สีผิวรอความยินยอม
        build_summaries(p)
        self.assertNotIn("ผอม", p["summaries"]["persona_text"])               # ไม่มีรูปลักษณ์ใน Dense
        self.assertFalse(ready_to_match(p))


class FlexTests(unittest.TestCase):
    def test_card_has_three_postback_buttons(self):
        cand = {"user_id": "U001", "display_name": "แพรว", "demographic": {"age": 24, "faculty": "วิทย์"},
                "persona": {"traits": [], "hobbies": []}, "summaries": {}}
        card = match_card(cand, 88, ["ทั้งคู่ชอบอ่านหนังสือ"], "ชวนคุยเรื่องหนังสือ")
        datas = [b["action"]["data"] for b in card["contents"]["footer"]["contents"]]
        self.assertEqual([d.split("&")[0] for d in datas], ["action=intro", "action=pass", "action=unmatch"])
        self.assertIn("88%", to_plain(card))


class OnboardingFlowTests(unittest.TestCase):
    def _send(self, event):
        line_api.outbox.clear()
        handlers.handle({"replyToken": "t", "source": {"userId": "Utest"}, **event})
        return [m for b in line_api.outbox for m in b["messages"]]

    def test_follow_consent_to_ready(self):
        self.assertIn("ยินยอม", self._send({"type": "follow"})[0]["text"])
        self._send({"type": "postback", "postback": {"data": "action=consent&v=yes"}})
        for ans in ("หญิง", "ชาย", "21", "พยาบาล"):
            out = self._send({"type": "message", "message": {"type": "text", "text": ans}})
        self.assertIn("เรียบร้อย", out[0]["text"])
        u = storage.get_line_user("Utest")
        p = storage.load_profile(u["user_id"])
        self.assertEqual((p["demographic"]["gender"], p["demographic"]["seeking"], p["demographic"]["age"]), ("F", ["M"], 21))
        self.assertEqual(u["state"], "ready")
        self._send({"type": "message", "message": {"type": "text", "text": "ลบข้อมูลของฉัน"}})
        self.assertIsNone(storage.get_line_user("Utest"))


class MutualIntroTests(unittest.TestCase):
    """ทำความรู้จักแบบยินยอมทั้งสองฝ่าย: ช่องทางติดต่อไม่หลุดถ้าอีกฝ่ายไม่ยินยอม"""

    def _send(self, uid, event):
        line_api.outbox.clear()
        handlers.handle({"replyToken": "t", "source": {"userId": uid}, **event})
        return [(b["to"], m) for b in line_api.outbox for m in b["messages"]]

    def _onboard(self, uid, gender, seeking):
        self._send(uid, {"type": "follow"})
        self._send(uid, {"type": "postback", "postback": {"data": "action=consent&v=yes"}})
        for ans in (gender, seeking, "22", "วิทย์"):
            self._send(uid, {"type": "message", "message": {"type": "text", "text": ans}})
        return storage.get_line_user(uid)["user_id"]

    def _msg(self, uid, text):
        return self._send(uid, {"type": "message", "message": {"type": "text", "text": text}})

    def _post(self, uid, data):
        return self._send(uid, {"type": "postback", "postback": {"data": data}})

    def test_accept_exchanges_and_decline_hides(self):
        a = self._onboard("Ua", "ชาย", "หญิง")
        b = self._onboard("Ub", "หญิง", "ชาย")
        c = self._onboard("Uc", "หญิง", "ชาย")
        self._post("Ua", f"action=intro&target={b}")                 # ขอ ID ของ A ก่อน
        out = self._msg("Ua", "nont_a22")
        card = [m for to, m in out if to == "Ub" and m["type"] == "flex"]
        self.assertTrue(card, "B ต้องได้การ์ดคำขอ")
        self.assertNotIn("nont_a22", str(card), "การ์ดคำขอต้องไม่มี LINE ID ของ A")
        req = card[0]["contents"]["footer"]["contents"][0]["action"]["data"].split("req=")[1]
        self._post("Ub", f"action=accept&req={req}")
        out = self._msg("Ub", "praew.b21")
        self.assertIn("nont_a22", str([m for to, m in out if to == "Ub"]))    # B ได้ ID ของ A
        self.assertIn("praew.b21", str([m for to, m in out if to == "Ua"]))   # A ได้ ID ของ B

        storage.set_contact(c, "secret.c23")
        self._post("Ua", f"action=intro&target={c}")
        req = storage.find_intro(a, c)["id"]
        out = self._post("Uc", f"action=decline&req={req}")
        to_a = str([m for to, m in out if to == "Ua"])
        self.assertIn("ยังไม่สะดวก", to_a)
        self.assertNotIn("secret.c23", to_a, "A ต้องไม่ได้ ID ของ C เมื่อ C ไม่ยินยอม")
        self.assertEqual(storage.find_intro(a, c)["status"], "declined")


if __name__ == "__main__":
    unittest.main()
