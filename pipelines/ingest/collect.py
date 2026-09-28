"""เก็บเอกสารใหม่จากเว็บที่เชื่อถือได้ -> PDF พร้อมหัวอ้างอิง (ขั้น staging ก่อนเข้า sources.py)

- รายการแหล่ง: data/new_docs/candidates.json (ผู้ดูแลตรวจ/ยืนยันก่อน)
- หน้าเว็บ: ใช้ตัวดึงข้อความเดิม (web.html_to_text) = ข้อความจากต้นฉบับตรงๆ ไม่มีการสรุปหรือแต่งเพิ่ม
- ไฟล์ PDF ต้นทาง (ThaiJO/DLTV): ดาวน์โหลดตามเดิม แล้วตรวจว่ามี text layer หรือต้อง OCR
- ผลลัพธ์: data/<ชื่อไฟล์ภาษาไทย>.pdf (ช่อง "file" ใน candidates.json) + data/new_docs/report.json
  (ความยาว/สัดส่วนภาษาไทย/ตัวอย่างต้นท้าย ให้ตรวจก่อนสกัด)

รัน: python -m pipelines.ingest.collect [id ...]
"""
import datetime
import json
import re
import sys
import urllib.request

import pymupdf

from ..common.paths import DATA
from .web import html_to_text

OUT = DATA / "new_docs"
RAW = OUT / "raw"
FONT = "/System/Library/Fonts/Supplemental/Sathu.ttf"     # ฟอนต์ไทย TTF ในเครื่อง (PyMuPDF จัดสระ/วรรณยุกต์ถูก)
UA = {"User-Agent": "Mozilla/5.0 (research; PSU Dealing)"}
MARGIN = 50
MIN_CHARS = 800         # สั้นกว่านี้ = น่าจะดึงเนื้อหาไม่ครบ (เว็บใช้ JS / หน้า infographic)


# ท้ายบทความ: เครดิตผู้เขียน/แท็ก/รายการอ้างอิง/ลิงก์บทความอื่น -> ไม่ใช่เนื้อหา ตัดทิ้ง (เฉพาะช่วงท้าย 40%)
TAIL_MARKERS = ("บทความโดย", "บทความวิชาการ", "อ้างอิงข้อมูลจาก", "บทความจากสารคดี", "รายการอ้างอิง", "อ้างอิง", "เอกสารอ้างอิง", "ค้นหาแพทย์และนักบำบัด",
                "เรื่องที่คุณอาจสนใจ", "อัปเดตข้อมูลแวดวงวิทยาศาสตร์", "ข่าวโดย", "ภาพจาก", "Reference",
                "แหล่งข้อมูลอ้างอิง", "“รอบรู้ ดูกระแส", "🎧", "Thai PBS Verify")
RE_JUNK_LINE = re.compile(r"^(📌\s*อ่าน|[\d,]+(\s*Views)?$|Views$|\|$|♥+$|02 725 9595)")


def trim(text, cut_from=None):
    """ตัดส่วนท้ายที่ไม่ใช่เนื้อหา (นับตำแหน่งตามจำนวนตัวอักษร: รายการลิงก์สั้นๆ ท้ายหน้าทำให้นับย่อหน้าเพี้ยน)
    cut_from = ข้อความเฉพาะแหล่ง (ใน candidates.json) ที่ให้ตัดตั้งแต่ตรงนั้น"""
    paras = [p.strip() for p in text.split("\n\n") if p.strip() and not RE_JUNK_LINE.match(p.strip())]
    total, pos = sum(map(len, paras)), 0
    for i, p in enumerate(paras):
        if (cut_from and p.startswith(cut_from)) or (pos >= total * 0.6 and p.startswith(TAIL_MARKERS)):
            paras = paras[:i]
            break
        pos += len(p)
    return "\n\n".join(paras).strip()


def _download(url, dest):
    if not dest.exists():
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            dest.write_bytes(r.read())
    return dest.read_bytes()


def _thai_ratio(text):
    letters = [c for c in text if c.isalpha()]
    return round(sum("฀" <= c <= "๿" for c in letters) / max(1, len(letters)), 2)


def _pages(doc, blocks):
    """วางทีละย่อหน้า ไม่พอหน้าให้ขึ้นหน้าใหม่ / ย่อหน้ายาวเกินหนึ่งหน้าให้แบ่งครึ่งที่ช่องว่าง"""
    page, y = None, None
    queue = list(blocks)
    while queue:
        text, size = queue.pop(0)
        if page is None or y > page.rect.height - MARGIN - size * 3:   # เหลือไม่ถึง 2 บรรทัด -> หน้าใหม่
            page, y = doc.new_page(), MARGIN
        rect = pymupdf.Rect(MARGIN, y, page.rect.width - MARGIN, page.rect.height - MARGIN)
        left = page.insert_textbox(rect, text, fontfile=FONT, fontname="th", fontsize=size, lineheight=1.5)
        if left >= 0:
            y = page.rect.height - MARGIN - left + size * 0.8
        elif y > MARGIN:
            page = None                                   # ไม่พอ -> หน้าใหม่แล้ววางซ้ำ
            queue.insert(0, (text, size))
        else:
            cut = text.rfind(" ", 0, len(text) // 2) if " " in text else len(text) // 2
            queue[:0] = [(text[:cut].strip(), size), (text[cut:].strip(), size)]


def to_pdf(c, text, dest):
    """หน้าแรกขึ้นด้วยหัวอ้างอิง (ชื่อ/หน่วยงาน/URL/วันที่เข้าถึง) แล้วตามด้วยเนื้อหาทีละย่อหน้า
    ใช้ insert_textbox (ไม่จัดรูป glyph) -> text layer ตรงกับต้นฉบับทุกตัวอักษร
    วัดจริง: Story/HTML (จัดรูป glyph) ทำไม้เอก/โท/ทัณฑฆาตหายจาก text layer ~7% ทุกฟอนต์ไทยในเครื่อง"""
    today = datetime.date.today().isoformat()
    head = [(c["title"], 16), (f"ที่มา: {c['org']}", 10), (c["url"], 8), (f"เข้าถึงเมื่อ {today}", 10)]
    body = [(p.strip(), 12) for p in text.split("\n\n") if p.strip()]
    with pymupdf.open() as doc:
        _pages(doc, head + body)
        doc.set_metadata({"title": c["title"], "author": c["org"], "subject": c["url"]})
        doc.save(dest)


def collect(c) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    row = {"id": c["id"], "file": c["file"], "url": c["url"], "title": c["title"], "org": c["org"]}
    if c.get("kind") == "pdf":
        raw = RAW / f"{c['id']}.pdf"
        data = _download(c["url"], raw)
        if not data.startswith(b"%PDF"):
            return {**row, "status": "ไม่ใช่ไฟล์ PDF (ลิงก์อาจเปลี่ยน)"}
        with pymupdf.open(raw) as doc:
            text = "\n\n".join(p.get_text() for p in doc)
            row["pages"] = len(doc)
        (DATA / c["file"]).write_bytes(data)                               # ใช้ PDF ต้นฉบับตรงๆ
    else:
        raw = RAW / f"{c['id']}.html"
        html = _download(c["url"], raw).decode("utf-8", errors="ignore")
        text = html_to_text(html)
        text = trim(re.sub(r"\n{3,}", "\n\n", text).strip(), c.get("cut_from"))
        if len(text) >= MIN_CHARS or c.get("short_ok"):
            to_pdf(c, text, DATA / c["file"])
    thai = _thai_ratio(text)
    ok = (len(text) >= MIN_CHARS or c.get("short_ok")) and thai >= 0.6
    return {**row, "chars": len(text), "thai_ratio": thai,
            "status": "ok" if ok else ("สั้นเกิน/ดึงไม่ครบ" if len(text) < MIN_CHARS else "ภาษาไทยน้อย (อาจต้อง OCR)"),
            "head": text[:160], "tail": text[-160:]}


def main():
    cands = json.loads((OUT / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    only = set(sys.argv[1:])
    rows = []
    for c in cands:
        if only and c["id"] not in only:
            continue
        try:
            row = collect(c)
        except Exception as e:                      # แหล่งเดียวล้มไม่ให้ทั้งชุดหยุด
            row = {"id": c["id"], "url": c["url"], "status": f"ดึงไม่ได้: {type(e).__name__}: {e}"}
        rows.append(row)
        print(f"  {row['id']:34} {row.get('chars', '-'):>6} ไทย {row.get('thai_ratio', '-')}  {row['status']}")
    report = OUT / "report.json"
    old = {r["id"]: r for r in json.loads(report.read_text(encoding="utf-8"))} if report.exists() else {}
    old.update({r["id"]: r for r in rows})
    report.write_text(json.dumps(list(old.values()), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
