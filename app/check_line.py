"""Offline preflight for the person hosting the LINE webhook."""
from .config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from .rich_menu import ASSETS, definition


def checks():
    image = ASSETS / "menu.jpg"
    menu = definition()
    results = {
        "channel_secret": bool(LINE_CHANNEL_SECRET),
        "channel_access_token": bool(LINE_CHANNEL_ACCESS_TOKEN),
        "rich_menu_image": image.is_file() and image.stat().st_size <= 1_000_000,
        "rich_menu_layout": menu["size"] == {"width": 1520, "height": 1035} and len(menu["areas"]) == 4,
    }
    return results


def main():
    results = checks()
    for name, ok in results.items():
        print(f"{'OK' if ok else 'MISSING'} {name}")
    if not all(results.values()):
        raise SystemExit(1)
    print("Ready to start webhook and publish rich menu (LINE API connection not tested).")


if __name__ == "__main__":
    main()
