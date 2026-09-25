"""Ingest pipeline: PDF -> extract -> clean -> section -> chunk -> tag -> data/processed/

รัน: python3 -m pipelines.ingest.run [--chunk-size 300 --overlap 0.15] [--source research_cu2561]
Output:
  data/processed/book_chunks.jsonl   chunk + metadata (พร้อม embed / สร้าง node BookChunk ใน Graph)
  data/processed/sections.json       โครงสร้าง section (debug/ตรวจสอบ)
  data/processed/ingest_report.json  สถิติคุณภาพข้อมูล + ตัวอย่างก่อน/หลัง clean
"""
import argparse
import json
from collections import Counter

from ..common.io_utils import write_json, write_jsonl
from ..common.paths import PROCESSED
from . import ocr
from .chunker import chunk_section, n_words
from .clean import clean_page_lines, strip_citations
from .extract import extract_pages, is_scanned
from .report import before_after, source_report
from .sectioner import merge_small, split_chapters
from .sources import SOURCES
from .tagger import tag


def load_pages(source):
    pages = extract_pages(source["file"])
    if not is_scanned(pages):
        return pages, "text"
    if ocr.available():
        return ocr.ocr_pages(source["file"]), "ocr"
    return pages, "needs_ocr"


def ingest(source, chunk_size, overlap, min_section_words):
    pages, mode = load_pages(source)
    stats = Counter()
    if mode == "needs_ocr":
        return [], [], source_report(source, pages, [], [], stats, "skipped: scanned PDF, OCR not installed"), None

    pages_lines = [(p["page"], clean_page_lines(p["text"], source["noise_patterns"], stats)) for p in pages]
    sections = merge_small(split_chapters(pages_lines, source), min_section_words, n_words)

    chunks = []
    for s_idx, sec in enumerate(sections):
        paras = [strip_citations(p, stats) for p in sec["paragraphs"]]
        for c_idx, text in enumerate(chunk_section(paras, chunk_size, overlap)):
            chunks.append({
                "chunk_id": f"{source['source_id']}_s{s_idx:02d}_c{c_idx:02d}",
                "source_id": source["source_id"],
                "doc_type": source["doc_type"],
                "title": source["title"],
                "year": source["year"],
                "chapter": sec["chapter"],
                "chapter_title": sec["chapter_title"],
                "section_title": sec["section_title"],
                "pages": sec["pages"],
                "text": text,
                "n_words": n_words(text),
                "n_chars": len(text),
                "lang": "th",
                **tag(text, sec["category"]),
            })
    sample_page = next((p for p in pages if "ส าคัญ" in p["text"]), pages[0])
    sample = before_after(sample_page["text"], "\n".join(l for l in dict(pages_lines)[sample_page["page"]] if l))
    return sections, chunks, source_report(source, pages, sections, chunks, stats, f"ok ({mode})"), sample


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
