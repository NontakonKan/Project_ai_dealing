"""รายงานคุณภาพข้อมูลหลัง ingest (ใช้ใส่ในรายงาน/สไลด์ ส่วน Data & Knowledge Base)"""
import statistics
from collections import Counter


def _dist(values):
    if not values:
        return {}
    q = statistics.quantiles(values, n=4) if len(values) > 1 else [values[0]] * 3
    return {"min": min(values), "p25": q[0], "median": q[1], "p75": q[2], "max": max(values),
            "mean": round(statistics.mean(values), 1)}


def source_report(source, pages, sections, chunks, stats, status):
    tagged = [c for c in chunks if c["concepts"]]
    return {
        "source_id": source["source_id"],
        "status": status,
        "pages_total": len(pages),
        "pages_used": len({p for s in sections for p in s["pages"]}),
        "n_sections": len(sections),
        "n_chunks": len(chunks),
        "chunk_words": _dist([c["n_words"] for c in chunks]),
        "chunks_with_concepts_pct": round(100 * len(tagged) / len(chunks), 1) if chunks else 0,
        "category_dist": dict(Counter(c["category"] for c in chunks)),
        "top_concepts": Counter(x for c in chunks for x in c["concepts"]).most_common(15),
        "cleaning": dict(stats),
    }


def before_after(raw_text: str, cleaned: str, n=400):
    """ตัวอย่างก่อน/หลัง clean สำหรับแสดงในรายงาน"""
    return {"before": raw_text[:n], "after": cleaned[:n]}
