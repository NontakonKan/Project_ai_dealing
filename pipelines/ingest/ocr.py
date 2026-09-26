"""OCR สำหรับไฟล์สแกน — 2 backend (เลือกอัตโนมัติ)

  vlm       : Vision LLM ผ่าน Ollama (qwen2.5vl) — ภาษาไทยแม่นมาก ~11 วินาที/หน้า บน M5 Pro ไม่ต้องติดตั้งเพิ่ม
  tesseract : brew install tesseract tesseract-lang (เร็วกว่า แต่ภาษาไทยผิดเยอะกว่า)

ผล OCR เก็บ cache ที่ data/processed/ocr/<source_id>.json -> รัน ingest ซ้ำไม่ต้อง OCR ใหม่
"""
import base64
import json
import re
import shutil
import time
import urllib.request

import pymupdf

from ..common.io_utils import read_json, write_json
from ..common.paths import DATA, PROCESSED
from ..llm.config import OLLAMA_URL

VLM_MODEL = "qwen2.5vl:latest"
VLM_PROMPT = "ถอดข้อความภาษาไทยทั้งหมดในภาพนี้ตามต้นฉบับทุกตัวอักษร ไม่แปล ไม่สรุป ไม่เพิ่มคำอธิบาย รักษาการขึ้นย่อหน้า"
VLM_RETRY_PROMPT = ("ภาพนี้เป็นหน้าหนังสือภาษาไทยที่ผู้ใช้เป็นเจ้าของ พิมพ์ข้อความทุกบรรทัดที่เห็นในภาพออกมาตรงตัว "
                    "ถ้าไม่มีข้อความเลยให้ตอบว่า EMPTY")
CACHE_DIR = PROCESSED / "ocr"
CORRECTIONS_FILE = DATA / "ocr_corrections.json"   # คำที่แก้ด้วยคน (ตรวจกับภาพต้นฉบับ)
# VLM บางครั้งตอบข้อความของตัวเองแทนการถอดข้อความ (ปฏิเสธ / บอกว่าไม่มีข้อความ / token หลุด)
RE_VLM_META = re.compile(r"(ขอ)?อภัย(ค่ะ|ครับ)?[ ,]*(แต่)?.*(ภาพ|ถอดข้อความ)|ไม่มีข้อความ(ภาษาไทย|ใดๆ)|โปรดส่งภาพ|^\s*system\s*$|^\s*EMPTY\s*$", re.M)


class OcrUnavailable(RuntimeError):
    pass


def _vlm_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
            return any(m["name"] == VLM_MODEL for m in json.loads(r.read())["models"])
    except OSError:
        return False


def available() -> str:
    if _vlm_available():
        return "vlm"
    if shutil.which("tesseract"):
        return "tesseract"
    return ""


def is_meta(text: str) -> bool:
    return bool(RE_VLM_META.search(text or ""))


def clean_vlm(text: str) -> str:
    """ตัดบรรทัดที่เป็นคำตอบของโมเดลเอง (ใช้ตอนอ่าน cache — cache เก็บผลดิบไว้ตรวจสอบย้อนหลัง)"""
    return "\n".join(line for line in (text or "").splitlines() if not RE_VLM_META.search(line))


def _vlm_page(page, dpi=150, prompt=VLM_PROMPT) -> str:
    img = base64.b64encode(page.get_pixmap(dpi=dpi).tobytes("png")).decode()
    body = {"model": VLM_MODEL, "stream": False, "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048},
            "messages": [{"role": "user", "content": prompt, "images": [img]}]}
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


def _tesseract_page(page, lang="tha+eng", dpi=300) -> str:
    tp = page.get_textpage_ocr(language=lang, dpi=dpi, full=True)
    return page.get_text(textpage=tp)


def ocr_pages(path, source_id, log=print) -> tuple:
    """คืน (pages, backend) — ใช้ cache ถ้ามี"""
    cache = CACHE_DIR / f"{source_id}.json"
    if cache.exists():
        c = read_json(cache)
        if c["backend"] == "vlm" and not c.get("retried") and _vlm_available():
            _retry_meta_pages(path, c, log)
            write_json(cache, c)
        pages = [{"page": p["page"], "text": clean_vlm(p["text"])} for p in c["pages"]]
        return apply_corrections(pages, source_id, log), f"{c['backend']} (cache)"
    backend = available()
    if not backend:
        raise OcrUnavailable("ไม่มี OCR: ollama pull qwen2.5vl หรือ brew install tesseract tesseract-lang")
    fn = _vlm_page if backend == "vlm" else _tesseract_page
    out, t0 = [], time.perf_counter()
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            out.append({"page": i, "text": fn(page)})
            log(f"    OCR {source_id} หน้า {i + 1}/{len(doc)} ({time.perf_counter() - t0:.0f}s)")
    c = {"backend": backend, "model": VLM_MODEL if backend == "vlm" else "tesseract",
         "seconds": round(time.perf_counter() - t0, 1), "pages": out}
    if backend == "vlm":
        _retry_meta_pages(path, c, log)
    write_json(cache, c)
    pages = [{"page": p["page"], "text": clean_vlm(p["text"])} for p in c["pages"]]
    return apply_corrections(pages, source_id, log), backend


def apply_corrections(pages, source_id, log=print) -> list:
    """แทนคำผิดตาม data/ocr_corrections.json — แจ้งเตือนถ้าหาคำเดิมไม่เจอ (เช่น OCR ใหม่แล้วข้อความเปลี่ยน)"""
    if not CORRECTIONS_FILE.exists():
        return pages
    fixes = read_json(CORRECTIONS_FILE).get(source_id, {}).get("pages", {})
    applied = missing = 0
    for p in pages:
        for wrong, right in fixes.get(str(p["page"]), []):
            if wrong in p["text"]:
                p["text"] = p["text"].replace(wrong, right)
                applied += 1
            else:
                missing += 1
    if fixes:
        log(f"    OCR corrections {source_id}: แก้ {applied} จุด" + (f", หาไม่เจอ {missing} จุด" if missing else ""))
    return pages


def _retry_meta_pages(path, cache: dict, log):
    """หน้าที่ VLM ตอบข้อความของตัวเอง -> ลองใหม่ด้วย dpi สูงขึ้น + prompt อีกแบบ (เก็บผลเดิมไว้ใน raw_first)"""
    with pymupdf.open(path) as doc:
        for p in cache["pages"]:
            if is_meta(p["text"]):
                first = p["text"]
                p["text"] = _vlm_page(doc[p["page"]], dpi=200, prompt=VLM_RETRY_PROMPT)
                p["raw_first"] = first
                log(f"    OCR retry หน้า {p['page'] + 1}: {'ยังไม่ได้' if is_meta(p['text']) else 'สำเร็จ'}")
    cache["retried"] = True
