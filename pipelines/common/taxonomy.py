"""โหลด taxonomy กลาง + lookup table ที่ใช้บ่อย"""
from functools import lru_cache

from .io_utils import read_json
from .paths import TAXONOMY_FILE

GROUPS = ("hobbies", "traits", "comm_styles", "attachment_styles", "love_languages",
          "love_components", "red_flags", "research_factors", "body_types", "skin_tones", "hygiene")
APPEARANCE_GROUPS = ("body_types", "skin_tones", "hygiene")


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


def group_of(tid: str) -> str:
    for g in GROUPS:
        if any(t["id"] == tid for t in load().get(g, [])):
            return g
    return ""


def appearance_ids() -> set:
    return {i for g in APPEARANCE_GROUPS for i in ids(g)}


def self_declared_only() -> set:
    return {t["id"] for g in GROUPS for t in load().get(g, []) if t.get("self_declared_only")}


def appearance_policy() -> dict:
    return load()["appearance_policy"]
