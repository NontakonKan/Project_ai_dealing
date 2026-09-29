"""Prepare/validate a LINE rich menu; --publish uploads and sets the default menu."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request

from .config import LINE_CHANNEL_ACCESS_TOKEN

ASSETS = Path(__file__).parent / "assets" / "rich_menu"
API = "https://api.line.me/v2/bot"
DATA_API = "https://api-data.line.me/v2/bot"


def definition():
    return {
        "size": {"width": 1520, "height": 1035},
        "selected": True,
        "name": "PSU Dealing — โปรไฟล์ / ถามบอต / ลบข้อมูล / หาคู่",
        "chatBarText": "เมนู",
        "areas": [
            {"bounds": {"x": 0, "y": 0, "width": 510, "height": 365},
             "action": {"type": "message", "label": "โปรไฟล์", "text": "โปรไฟล์ของฉัน"}},
            {"bounds": {"x": 0, "y": 365, "width": 510, "height": 325},
             "action": {"type": "message", "label": "ถามบอต", "text": "ถามบอต"}},
            {"bounds": {"x": 0, "y": 690, "width": 510, "height": 345},
             "action": {"type": "postback", "label": "ลบข้อมูล", "data": "action=delete_prompt",
                        "displayText": "ลบข้อมูล"}},
            {"bounds": {"x": 510, "y": 0, "width": 1010, "height": 1035},
             "action": {"type": "message", "label": "หาคู่", "text": "หาคู่ให้หน่อย"}},
        ],
    }


def request(method, path, payload=None, *, image=None):
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    body = None
    base = API
    if image is not None:
        base = DATA_API
        headers["Content-Type"] = "image/jpeg"
        body = image
    elif payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def publish():
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise ValueError("ตั้ง LINE_CHANNEL_ACCESS_TOKEN ใน .env ที่ root ก่อน publish")
    image = (ASSETS / "menu.jpg").read_bytes()
    if len(image) > 1_000_000:
        raise ValueError("Rich menu image must be at most 1 MB")
    menu = definition()
    request("POST", "/richmenu/validate", menu)
    try:
        previous = request("GET", "/user/all/richmenu").get("richMenuId")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        previous = None
    menu_id = request("POST", "/richmenu", menu)["richMenuId"]
    # Print IDs before uploading so interrupted deployments can be recovered.
    print(json.dumps({"created": menu_id, "previous_default": previous}, ensure_ascii=False), flush=True)
    request("POST", f"/richmenu/{menu_id}/content", image=image)
    # Only replace the default after the image is uploaded; keep the old menu for rollback.
    request("POST", f"/user/all/richmenu/{menu_id}")
    actual = request("GET", "/user/all/richmenu").get("richMenuId")
    if actual != menu_id:
        raise RuntimeError("Default rich menu verification failed")
    print(f"Default rich menu: {menu_id}")
    if previous:
        print(f"Rollback: python -m app.rich_menu --restore {previous}")
    return menu_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--restore", metavar="RICH_MENU_ID")
    args = parser.parse_args()
    try:
        if args.publish:
            publish()
        elif args.restore:
            if not LINE_CHANNEL_ACCESS_TOKEN:
                raise ValueError("ตั้ง LINE_CHANNEL_ACCESS_TOKEN ก่อน restore")
            if not args.restore.startswith("richmenu-") or not args.restore[9:].isalnum():
                raise ValueError("Invalid rich menu ID")
            request("POST", f"/user/all/richmenu/{args.restore}")
            print(f"Restored: {args.restore}")
        else:
            print(json.dumps(definition(), ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as exc:
        parser.exit(1, f"LINE API failed (HTTP {exc.code}). Check token/channel permissions and menu settings.\n")
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
