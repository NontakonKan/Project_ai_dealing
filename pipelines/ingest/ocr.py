"""OCR สำหรับไฟล์สแกน (ใช้ Tesseract ผ่าน PyMuPDF) — ต้องติดตั้ง: brew install tesseract tesseract-lang"""
import shutil

import pymupdf


class OcrUnavailable(RuntimeError):
    pass


def available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_pages(path, lang="tha+eng", dpi=300) -> list:
    if not available():
        raise OcrUnavailable("ไม่พบ tesseract — ติดตั้งด้วย `brew install tesseract tesseract-lang`")
    out = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            tp = page.get_textpage_ocr(language=lang, dpi=dpi, full=True)
            out.append({"page": i, "text": page.get_text(textpage=tp)})
    return out
