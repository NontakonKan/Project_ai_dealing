import unittest
from unittest.mock import patch

from app import handlers, intent, rich_menu


class RichMenuTests(unittest.TestCase):
    def test_areas_cover_image_without_overlap_and_route_commands(self):
        menu = rich_menu.definition()
        areas = [area["bounds"] for area in menu["areas"]]
        w, h = menu["size"]["width"], menu["size"]["height"]
        self.assertEqual(sum(a["width"] * a["height"] for a in areas), w * h)
        for i, a in enumerate(areas):
            self.assertTrue(0 <= a["x"] < a["x"] + a["width"] <= w)
            self.assertTrue(0 <= a["y"] < a["y"] + a["height"] <= h)
            for b in areas[i + 1:]:
                self.assertTrue(a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])
        self.assertEqual(intent.classify(menu["areas"][0]["action"]["text"]), "show_profile")
        self.assertEqual(intent.classify(menu["areas"][2]["action"]["text"]), "find_match")

    def test_bot_button_prompts_without_calling_model_or_saving_memory(self):
        event = {"type": "message", "source": {"userId": "L1"},
                 "message": {"type": "text", "text": "ถามบอต"}}
        with patch.object(handlers, "_user", return_value={"state": "ready"}), \
             patch.object(handlers.storage, "add_message") as save, \
             patch.object(handlers.conversation, "prepare") as memory:
            self.assertIn("พิมพ์คำถาม", handlers.dispatch(event)[0]["text"])
            save.assert_not_called()
            memory.assert_not_called()

    def test_publish_uploads_before_switching_default(self):
        with patch.object(rich_menu, "LINE_CHANNEL_ACCESS_TOKEN", "test"), \
             patch.object(rich_menu, "request", side_effect=[{}, {"richMenuId": "old"},
                          {"richMenuId": "new"}, {}, {}, {"richMenuId": "new"}]) as api, \
             patch("builtins.print"):
            self.assertEqual(rich_menu.publish(), "new")
            self.assertEqual(api.call_args_list[3].args, ("POST", "/richmenu/new/content"))
            self.assertEqual(api.call_args_list[4].args, ("POST", "/user/all/richmenu/new"))

    def test_upload_failure_keeps_previous_default(self):
        with patch.object(rich_menu, "LINE_CHANNEL_ACCESS_TOKEN", "test"), \
             patch.object(rich_menu, "request", side_effect=[{}, {"richMenuId": "old"},
                          {"richMenuId": "new"}, OSError("upload failed")]) as api, \
             patch("builtins.print"):
            with self.assertRaises(OSError):
                rich_menu.publish()
            self.assertFalse(any("/user/all/richmenu/" in c.args[1] for c in api.call_args_list))
