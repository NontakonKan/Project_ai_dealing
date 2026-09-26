"""ดึงบทความเว็บ -> ข้อความ (ใช้แหล่งที่เชื่อถือได้เป็นหลัก เช่น คณะจิตวิทยา จุฬาฯ)

- เก็บ HTML ดิบเป็น cache ที่ data/raw/web/<source_id>.html (ไม่ขึ้น git) -> รันซ้ำไม่ต้องดาวน์โหลดใหม่ + ตรวจย้อนหลังได้
- เลือกเฉพาะ container เนื้อหาบทความ (entry-content ฯลฯ) ตัดเมนู/footer/สคริปต์
"""
import urllib.request
from html.parser import HTMLParser

from ..common.paths import RAW

CACHE_DIR = RAW / "web"
CONTENT_MARKERS = ("entry-content", "single-blog-content", "article-content", "post-content")
BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "li", "br", "div", "section", "blockquote", "tr"}
SKIP = {"script", "style", "noscript", "nav", "footer", "header", "form", "aside", "figure", "button", "svg"}
BOILERPLATE = ("แชร์", "Share", "บทความที่เกี่ยวข้อง", "Related", "Tags", "อ่านต่อ", "Copyright")


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0           # >0 = อยู่ใน container เนื้อหา
        self.skip = 0
        self.found_container = False
        self.parts, self.fallback = [], []
        self._in_p = 0

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if self.depth:
            self.depth += tag not in ("br", "img", "hr", "meta", "link", "input")
        elif tag in ("div", "article", "section") and any(m in cls for m in CONTENT_MARKERS) and not self.found_container:
            self.depth, self.found_container = 1, True
        if tag in SKIP:
            self.skip += 1
        if tag == "p":
            self._in_p += 1
        if tag in BLOCK:
            (self.parts if self.depth else self.fallback).append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag == "p" and self._in_p:
            self._in_p -= 1
            self.fallback.append("\n")
        if self.depth and tag not in ("br", "img", "hr", "meta", "link", "input"):
            self.depth -= 1
        if tag in BLOCK and self.depth:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self.depth:
            self.parts.append(data)
        elif self._in_p:
            self.fallback.append(data)


def html_to_text(html: str) -> str:
    ex = _Extractor()
    ex.feed(html)
    raw = "".join(ex.parts if ex.found_container else ex.fallback)
    lines = [" ".join(line.split()) for line in raw.splitlines()]
    lines = [line for line in lines if line and not any(line.startswith(b) for b in BOILERPLATE)]
    return "\n\n".join(lines)


def fetch(source: dict) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{source['source_id']}.html"
    if not cache.exists():
        req = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0 (research; PSU Dealing)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            cache.write_bytes(r.read())
    return cache.read_text(encoding="utf-8", errors="ignore")


def fetch_pages(source: dict) -> list:
    """บทความเว็บ = 1 "หน้า" (ให้ขั้นตอนถัดไปเหมือน PDF ทุกอย่าง)"""
    return [{"page": 0, "text": html_to_text(fetch(source))}]
