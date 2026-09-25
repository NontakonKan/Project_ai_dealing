"""ทำความสะอาดข้อความภาษาไทยจาก PDF

ปัญหาที่พบจริงในไฟล์งานวิจัย:
  1. สระอำถูกแยกเป็น "พยัญชนะ + ช่องว่าง + า" เช่น "ส าคัญ" -> "สำคัญ"
     (แก้ได้แน่นอน เพราะภาษาไทยไม่มีคำที่ขึ้นต้นด้วย "า")
  2. header/footer/เลขหน้า ซ้ำทุกหน้า
  3. บรรทัดถูกตัดกลางประโยค -> ต้องต่อบรรทัด
  4. เลขอ้างอิงท้ายข้อความ เช่น "(19)" เป็น noise สำหรับ embedding
"""
import re
from collections import Counter

from pythainlp.util import normalize

THAI = "฀-๿"
RE_SARA_AM = re.compile(r"([ก-ฮ][่-๋]?)[ \t]+า")
RE_CITATION = re.compile(r"\((\d{1,2})(\s*[,\-–]\s*\d{1,2})*\)")
RE_SPACES = re.compile(r"[ \t ]+")


def fix_sara_am(text: str) -> tuple:
    return RE_SARA_AM.subn(lambda m: m.group(1) + "ำ", text)


def clean_page_lines(text: str, noise_patterns, stats: Counter) -> list:
    """คืนรายการบรรทัดที่สะอาดแล้วของ 1 หน้า ('' = ย่อหน้าใหม่)"""
    text, n = fix_sara_am(text)
    stats["sara_am_fixed"] += n
    noise = [re.compile(p) for p in noise_patterns]
    out = []
    for raw in text.splitlines():
        line = RE_SPACES.sub(" ", raw).strip()
        if line and any(p.match(line) for p in noise):
            stats["noise_lines_removed"] += 1
            continue
        out.append(normalize(line) if line else "")
    return out


def join_lines(lines) -> list:
    """ต่อบรรทัดเป็นย่อหน้า: ไทย-ไทยต่อชิดกัน, อื่นๆ คั่นด้วยช่องว่าง"""
    paras, cur = [], ""
    for line in lines:
        if not line:
            if cur:
                paras.append(cur)
            cur = ""
            continue
        if cur and re.search(f"[{THAI}]$", cur) and re.match(f"^[{THAI}]", line):
            cur += line
        else:
            cur = f"{cur} {line}".strip()
    if cur:
        paras.append(cur)
    return paras


def strip_citations(text: str, stats: Counter) -> str:
    text, n = RE_CITATION.subn("", text)
    stats["citations_removed"] += n
    return RE_SPACES.sub(" ", text).strip()
