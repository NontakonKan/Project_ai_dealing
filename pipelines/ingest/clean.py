"""ทำความสะอาดข้อความภาษาไทยจาก PDF

ปัญหาที่พบจริงในไฟล์งานวิจัย:
  1. สระอำถูกแยกเป็น "พยัญชนะ + ช่องว่าง + า" เช่น "ส าคัญ" -> "สำคัญ"
     (แก้ได้แน่นอน เพราะภาษาไทยไม่มีคำที่ขึ้นต้นด้วย "า")
  2. header/footer/เลขหน้า ซ้ำทุกหน้า
  3. บรรทัดถูกตัดกลางประโยค -> ต้องต่อบรรทัด
  4. เลขอ้างอิงท้ายข้อความ เช่น "(19)" เป็น noise สำหรับ embedding
  5. วรรณยุกต์/สระถูกเก็บเป็นอักษรใน Private Use Area (U+F700–F71A) ของฟอนต์ไทย เช่น "ได\uf70bยิน"
     -> มองไม่เห็นแต่ตัดคำ/embedding พัง -> แปลงกลับเป็นอักษรไทยมาตรฐาน ("ได้ยิน") ตามตาราง Thai PUA
"""
import re
from collections import Counter

from pythainlp.util import normalize

THAI = "฀-๿"
RE_SARA_AM = re.compile(r"([ก-ฮ][่-๋]?)[ \t]+า")
RE_CITATION = re.compile(r"\((\d{1,2})(\s*[,\-–]\s*\d{1,2})*\)")
RE_SPACES = re.compile(r"[ \t ]+")


# Thai PUA (ตำแหน่งวรรณยุกต์/สระที่ถูกเลื่อนในฟอนต์) -> อักษรมาตรฐาน
PUA_THAI = str.maketrans({0xF700: "ฐ", 0xF701: "ิ", 0xF702: "ี", 0xF703: "ึ", 0xF704: "ื", 0xF705: "่", 0xF706: "้",
                          0xF707: "๊", 0xF708: "๋", 0xF709: "์", 0xF70A: "่", 0xF70B: "้", 0xF70C: "๊", 0xF70D: "๋",
                          0xF70E: "์", 0xF70F: "ญ", 0xF710: "ั", 0xF711: "ํ", 0xF712: "็", 0xF713: "่", 0xF714: "้",
                          0xF715: "๊", 0xF716: "๋", 0xF717: "์", 0xF718: "ุ", 0xF719: "ู", 0xF71A: "ฺ"})
RE_PUA = re.compile("[\uf700-\uf71a]")


def fix_pua(text: str) -> tuple:
    return text.translate(PUA_THAI), len(RE_PUA.findall(text))


def fix_sara_am(text: str) -> tuple:
    return RE_SARA_AM.subn(lambda m: m.group(1) + "ำ", text)


def clean_page_lines(text: str, noise_patterns, stats: Counter) -> list:
    """คืนรายการบรรทัดที่สะอาดแล้วของ 1 หน้า ('' = ย่อหน้าใหม่)"""
    text, n = fix_pua(text)
    stats["pua_fixed"] += n
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
