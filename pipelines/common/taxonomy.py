"""โหลด taxonomy กลาง + lookup table ที่ใช้บ่อย"""
from functools import lru_cache

from .io_utils import read_json
from .paths import TAXONOMY_FILE

GROUPS = ("hobbies", "traits", "comm_styles", "attachment_styles", "love_languages",
          "love_components", "red_flags", "research_factors")


@lru_cache(maxsize=1)
def load() -> dict:
    return read_json(TAXONOMY_FILE)


def ids(group: str) -> list:
    return [t["id"] for t in load()[group]]


def labels() -> dict:
    return {t["id"]: t["label_th"] for g in GROUPS for t in load().get(g, [])}


def aliases() -> dict:
    return {t["id"]: t.get("aliases", []) for g in GROUPS for t in load().get(g, [])}


def rules() -> list:
    return load()["compatibility_rules"]
