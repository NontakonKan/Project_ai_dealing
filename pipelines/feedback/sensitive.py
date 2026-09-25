"""ตรวจคำเรื่องรูปลักษณ์/สีผิว/สุขอนามัยด้วยคีย์เวิร์ด (ไม่พึ่ง LLM)

ใช้ 2 ที่:
  1. guard: red flag ที่ evidence เป็นคำรูปลักษณ์ = LLM จัดหมวดผิด -> ทิ้ง (กัน "อ้วนไป" กลายเป็น rf:disrespect)
  2. fallback: LLM ตกหล่นคำรูปลักษณ์ในเหตุผลเลิกคุย -> เติมให้

คำยาว (> 4 ตัวอักษร เช่น "ผิวขาว", "หุ่นหมี") ไม่กำกวม -> match ได้เลย
คำสั้น ("ขาว", "ดำ", "อ้วน") กำกวม -> ต้องอยู่ที่ขอบคำ + ไม่ติดคำที่บอกว่าเป็นสิ่งของ ("ข้าวขาว", "รูปขาวดำ")
  mode="chat"    ต้องมีคำบ่งว่าพูดถึงคนอยู่ข้างหน้า ("คน", "ผิว", "หุ่น")
  mode="unmatch" ทั้งประโยคพูดถึงอีกฝ่ายอยู่แล้ว -> ไม่ต้องมีคำบ่ง
"""
from functools import lru_cache

from pythainlp.tokenize import word_tokenize

from ..common import taxonomy

SHORT_LEN = 4
NON_PERSON = {"ข้าว", "รูป", "ภาพ", "กาแฟ", "เสื้อ", "กางเกง", "รถ", "แมว", "หมา", "ไวน์", "ช็อกโกแลต", "สี", "จอ",
              "ทีวี", "หนัง", "ฟิล์ม", "ขนม", "ไก่", "หมู", "ปลา", "ขาวดำ", "ดำขาว", "ถ่าน", "ผม"}
COLOR_WORDS = {"ขาว", "ดำ"}
PERSON_CUE = {"คน", "ผิว", "หุ่น", "ตัว", "สเปก", "แฟน", "ผู้ชาย", "ผู้หญิง", "สาว", "หนุ่ม", "ชอบ", "เป็น"}


@lru_cache(maxsize=1)
def _lexicon():
    labels, out = taxonomy.labels(), []
    for tid in taxonomy.appearance_ids():
        for term in {*taxonomy.aliases().get(tid, []), labels[tid]}:
            if "/" not in term:
                out.append((term.lower(), tid))
    return sorted(out, key=lambda x: -len(x[0]))  # คำยาวก่อน ("ผิวขาว" ก่อน "ขาว")


def _tokens(text):
    toks, spans, pos = word_tokenize(text, engine="newmm", keep_whitespace=True), [], 0
    for t in toks:
        spans.append((pos, pos + len(t), t))
        pos += len(t)
    return spans


def _has_non_person(word):
    return any(n in word for n in NON_PERSON)


def _short_ok(spans, start, end, mode):
    idx = [k for k, (a, b, _) in enumerate(spans) if a == start]
    if not idx or not any(b == end for _, b, _ in spans):
        return False                               # ไม่อยู่ที่ขอบคำ
    k = idx[0]
    words = [t.strip() for _, _, t in spans]
    prev = [w for w in words[max(0, k - 3):k] if w]
    nxt = next((w for w in words[k + 1:] if w), "")
    near = [prev[-1] if prev else "", nxt]
    if any(n and (_has_non_person(n) or n in COLOR_WORDS) for n in near) or words[k] in NON_PERSON:
        return False                               # "กินข้าว|ขาว", "ถ่ายรูป|ขาว|ดำ"
    return mode == "unmatch" or any(w in PERSON_CUE for w in prev)


def detect(text: str, mode: str = "unmatch") -> list:
    """คืน [{"id", "evidence"}] ของคำรูปลักษณ์ที่พบ (ไม่ซ้ำ id)"""
    low = text.lower()
    spans = _tokens(low)
    found, used = {}, []
    for term, tid in _lexicon():
        i = low.find(term)
        while i != -1:
            s, e = i, i + len(term)
            overlap = any(a < e and s < b for a, b in used)
            if not overlap and (len(term) > SHORT_LEN or _short_ok(spans, s, e, mode)):
                used.append((s, e))
                found.setdefault(tid, {"id": tid, "evidence": text[s:e]})
            i = low.find(term, i + 1)
    return list(found.values())


def is_appearance(evidence: str) -> bool:
    return bool(detect(evidence or "", mode="unmatch"))
