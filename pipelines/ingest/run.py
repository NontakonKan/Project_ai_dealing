"""Ingest pipeline: PDF -> extract -> clean -> section -> chunk -> tag -> data/processed/

รัน: python3 -m pipelines.ingest.run [--chunk-size 300 --overlap 0.15] [--source research_cu2561]
Output:
  data/processed/book_chunks.jsonl   chunk + metadata (พร้อม embed / สร้าง node BookChunk ใน Graph)
  data/processed/sections.json       โครงสร้าง section (debug/ตรวจสอบ)
  data/processed/ingest_report.json  สถิติคุณภาพข้อมูล + ตัวอย่างก่อน/หลัง clean
"""
import argparse
import json
import re
from collections import Counter

from ..common.io_utils import write_json, write_jsonl
from ..common.paths import PROCESSED
from . import ocr, web
from .chunker import chunk_section, n_words
from .clean import clean_page_lines, strip_citations
from .extract import extract_pages, is_scanned
from .report import before_after, source_report
from .sectioner import merge_small, split_chapters
from .sources import SOURCES
from .tagger import tag


def redact(text, rules, stats):
    """ลบข้อมูลส่วนบุคคลตาม regex ของแต่ละแหล่ง (เช่น ชื่อ-จังหวัดของผู้ถาม) ก่อนตัด chunk"""
    for pattern, repl in rules:
        text, n = re.subn(pattern, repl, text)
        stats["redacted"] += n
    return text


def name_rules(pages_lines, source, stats) -> list:
    """หาชื่อผู้ถามจากตัวเอกสารตอนรัน (ไม่เก็บชื่อไว้ในโค้ด/config) แล้วสร้างกฎลบ "น้อง<ชื่อ>" / "คุณ<ชื่อ>" ทั้งเอกสาร"""
    pats = source.get("name_capture", [])
    if not pats:
        return []
    text = re.sub(r"\s+", " ", " ".join(l for _, ls in pages_lines for l in ls))
    stop = set(source.get("name_stopwords", []))
    names = {n for p in pats for n in re.findall(p, text) if len(n) >= 2 and n not in stop}
    stats["names_found"] += len(names)
    # ชื่อสั้น (เอ, ดิว) ต้องไม่ตามด้วยพยัญชนะ -> ไม่ตัด "น้องเอง"
    return [(r"(น้อง|คุณ)" + re.escape(n) + r"(?![ก-ฮ])", r"\1") for n in sorted(names, key=len, reverse=True)]


def _load_file(path, cache_id):
    pages = extract_pages(path)
    if not is_scanned(pages):
        return pages, "text"
    if ocr.available() or (ocr.CACHE_DIR / f"{cache_id}.json").exists():
        pages, backend = ocr.ocr_pages(path, cache_id)
        return pages, f"ocr:{backend}"
    return pages, "needs_ocr"


def load_pages(source):
    if source.get("url"):
        return web.fetch_pages(source), "web"
    if source.get("files"):   # เอกสารเดียวที่ถูกแยกเป็นหลายไฟล์ (เช่น วิทยานิพนธ์รายบท) -> ต่อเลขหน้าเป็นเล่มเดียว
        pages, modes = [], set()
        for n, path in enumerate(source["files"], 1):
            part, mode = _load_file(path, f"{source['source_id']}_{n}")
            offset = len(pages)
            pages += [{**x, "page": x["page"] + offset} for x in part]
            modes.add(mode)
        return pages, ("needs_ocr" if "needs_ocr" in modes else "+".join(sorted(modes)))
    pages, mode = _load_file(source["file"], source["source_id"])
    if source.get("pages"):   # ใช้เฉพาะช่วงหน้าที่กำหนด (นับแบบเลขหน้าจริง เริ่ม 1) เช่น ตัดหน้าขนาดยาออก
        lo, hi = source["pages"]
        pages = [x for x in pages if lo <= x["page"] + 1 <= hi]
    return pages, mode


def ingest(source, chunk_size, overlap, min_section_words):
    pages, mode = load_pages(source)
    stats = Counter()
    if mode == "needs_ocr":
        return [], [], source_report(source, pages, [], [], stats, "skipped: scanned PDF, OCR not installed"), None

    pages_lines = [(p["page"], clean_page_lines(p["text"], source["noise_patterns"], stats)) for p in pages]
    sections = merge_small(split_chapters(pages_lines, source), min_section_words, n_words)
    rules = source.get("redact", []) + name_rules(pages_lines, source, stats)

    chunks = []
    for s_idx, sec in enumerate(sections):
        paras = [redact(strip_citations(p, stats), rules, stats) for p in sec["paragraphs"]]
        for c_idx, text in enumerate(chunk_section(paras, source.get("chunk_size", chunk_size), overlap)):
            chunks.append({
                "chunk_id": f"{source['source_id']}_s{s_idx:02d}_c{c_idx:02d}",
                "source_id": source["source_id"],
                "doc_type": source["doc_type"],
                "title": source["title"],
                "year": source["year"],
                "url": source.get("url"),
                "source_quality": source.get("source_quality", "document"),
                "chapter": sec["chapter"],
                "chapter_title": sec["chapter_title"],
                "section_title": sec["section_title"],
                "pages": sec["pages"],
                "text": text,
                "n_words": n_words(text),
                "n_chars": len(text),
                "lang": "th",
                **tag(text, sec["category"], concepts=source.get("tag_concepts", True)),
            })
    chunks = dedupe(chunks, stats)
    sample_page = next((p for p in pages if "ส าคัญ" in p["text"]), pages[0])  # ตัวอย่าง before/after
    sample = before_after(sample_page["text"], "\n".join(l for l in dict(pages_lines)[sample_page["page"]] if l))
    return sections, chunks, source_report(source, pages, sections, chunks, stats, f"ok ({mode})"), sample


def dedupe(chunks, stats):
    """ตัด chunk ที่ข้อความซ้ำกันทุกตัวอักษร (ไม่นับช่องว่าง) ภายในเอกสารเดียวกัน เก็บอันแรกไว้
    วัดจริง: ภาคผนวกวิทยานิพนธ์ความดึงดูด พิมพ์แบบสอบถามชุดเดิมซ้ำ 5 เงื่อนไขการทดลอง -> 18 chunk ซ้ำ
    ซึ่งแย่งที่ใน top-k ของการค้น (chunk_id ที่ถูกตัดจะเว้นว่าง ไม่เลื่อนเลข เพื่อให้ id เดิมคงที่)"""
    seen, kept = set(), []
    for c in chunks:
        key = "".join(c["text"].split())
        if key in seen:
            stats["duplicate_chunks_removed"] += 1
            continue
        seen.add(key)
        kept.append(c)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-size", type=int, default=300, help="จำนวนคำ (PyThaiNLP) ต่อ chunk")
    ap.add_argument("--overlap", type=float, default=0.15)
    ap.add_argument("--min-section-words", type=int, default=80, help="section สั้นกว่านี้รวมกับ section ถัดไป")
    ap.add_argument("--source", help="ingest เฉพาะ source_id นี้")
    args = ap.parse_args()

    all_chunks, all_sections, reports, samples = [], {}, [], {}
    for src in SOURCES:
        if args.source and src["source_id"] != args.source:
            continue
        sections, chunks, rep, sample = ingest(src, args.chunk_size, args.overlap, args.min_section_words)
        all_chunks += chunks
        all_sections[src["source_id"]] = [{k: v for k, v in s.items() if k != "paragraphs"} | {"n_paragraphs": len(s["paragraphs"])} for s in sections]
        reports.append(rep)
        if sample:
            samples[src["source_id"]] = sample
        print(f"[{rep['status']}] {src['source_id']}: {rep['n_sections']} sections, {rep['n_chunks']} chunks")

    write_jsonl(PROCESSED / "book_chunks.jsonl", all_chunks)
    write_json(PROCESSED / "sections.json", all_sections)
    write_json(PROCESSED / "ingest_report.json", {"config": vars(args), "sources": reports, "before_after": samples})
    print(json.dumps(reports, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
