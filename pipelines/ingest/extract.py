"""ดึงข้อความรายหน้าจาก PDF (PyMuPDF) + ตรวจว่าเป็นไฟล์สแกนหรือไม่"""
import pymupdf

MIN_CHARS_PER_PAGE = 50


def extract_pages(path) -> list:
    with pymupdf.open(path) as doc:
        return [{"page": i, "text": p.get_text()} for i, p in enumerate(doc)]


def is_scanned(pages) -> bool:
    avg = sum(len(p["text"].strip()) for p in pages) / max(1, len(pages))
    return avg < MIN_CHARS_PER_PAGE
