"""ตรวจความถูกต้องของ taxonomy + concept_lexicon (รันทุกครั้งหลังแก้ไฟล์)

  python -m pipelines.common.validate_taxonomy
ตรวจ: id ซ้ำ / prefix ตรงหมวด / กฎอ้าง id ที่มีจริง / lexicon อ้าง id ที่มีจริง / alias ชนข้าม id / หมวดใน JSON ที่ GROUPS ไม่รู้จัก
"""
import sys
from collections import defaultdict

from . import taxonomy
from .io_utils import read_json
from .paths import LEXICON_FILE

PREFIX = {"hobbies": "hobby", "traits": "trait", "comm_styles": "comm", "attachment_styles": "attach",
          "love_languages": "ll", "love_components": "love", "red_flags": "rf", "research_factors": "factor",
          "body_types": "body", "skin_tones": "skin", "hygiene": "hygiene"}
NON_GROUP_KEYS = {"version", "description", "sources", "compatibility_rules", "appearance_policy"}


def check() -> tuple:
    tax, errors, warnings = taxonomy.load(), [], []
    all_ids, alias_owner = set(), defaultdict(set)
    for key, val in tax.items():
        if key not in NON_GROUP_KEYS and key not in taxonomy.GROUPS:
            errors.append(f"หมวด '{key}' ไม่อยู่ใน GROUPS ของ common/taxonomy.py -> โค้ดจะมองไม่เห็น")
    for g in taxonomy.GROUPS:
        for t in tax.get(g, []):
            tid = t["id"]
            if tid in all_ids:
                errors.append(f"id ซ้ำ: {tid}")
            all_ids.add(tid)
            if tid.split(":")[0] != PREFIX.get(g):
                errors.append(f"{tid} อยู่หมวด {g} แต่ prefix ควรเป็น {PREFIX.get(g)}:")
            for a in t.get("aliases", []):
                alias_owner[a.lower()].add(tid)
    for r in tax["compatibility_rules"]:
        for side in ("a", "b"):
            if r[side] not in all_ids:
                errors.append(f"กฎอ้าง id ที่ไม่มี: {r[side]}")
    for g in taxonomy.appearance_policy()["groups"]:
        if g not in taxonomy.GROUPS:
            errors.append(f"appearance_policy อ้างหมวดที่ไม่มี: {g}")
    lex = read_json(LEXICON_FILE)
    for cid in lex["concepts"]:
        if cid not in all_ids:
            errors.append(f"concept_lexicon อ้าง id ที่ไม่มี: {cid}")
    for a, owners in alias_owner.items():
        if len(owners) > 1:
            warnings.append(f"alias '{a}' ชนกัน: {sorted(owners)}")
    return errors, warnings, len(all_ids)


def main():
    errors, warnings, n = check()
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{n} ids, {len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
