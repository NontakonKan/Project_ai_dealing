"""เตรียมภาพก่อน OCR + เรียก VLM

วัดจริงกับหน้าที่ถอดด้วยมือ 4 หน้า (pipelines/ingest/ocr_eval.py):
  ทั้งหน้า 150 dpi (เดิม)                      CER 7.99%  WER 14.59%
  ทั้งหน้า 150 dpi + ตัดตราดาวน์โหลดขอบล่าง     CER 4.28%  WER 13.31%   <- ใช้อันนี้ (หน้าตาราง 19.9% -> 6.6%)
  + ขาวดำ/เพิ่มความคมชัด                       CER 4.70%
  200 dpi                                      CER 6.98%
  หั่นเป็นแถบ 2-3 แถบ                          CER 13.7-23.7%  (โมเดลรวมบรรทัด ต่อแถบกลับไม่ได้ + อ่านผิดมากขึ้น)
"""
import base64
import io
import json
import urllib.request

import pymupdf
from PIL import Image, ImageFilter, ImageOps

from ..llm.config import OLLAMA_URL

STAMP_CUT = 0.06        # ตัดขอบล่าง 6% (ตรา "โดย ผู้ใช้ทั่วไป / ดาวน์โหลดเมื่อ ..." ของคลังวิทยานิพนธ์)


def render(page, dpi=150, clip=None, enhance=False) -> bytes:
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if enhance:
        img = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1).filter(ImageFilter.SHARPEN)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def body_clip(page, cut=STAMP_CUT):
    r = page.rect
    return pymupdf.Rect(r.x0, r.y0, r.x1, r.y1 - r.height * cut)


def vlm(png: bytes, model, prompt, num_predict=2048) -> str:
    body = {"model": model, "stream": False, "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": num_predict},
            "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(png).decode()]}]}
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


def ocr_page(page, model, prompt, dpi=150) -> str:
    return vlm(render(page, dpi, body_clip(page)), model, prompt)
