"""แบ่งเอกสารเป็น section ตามโครงสร้าง (บทที่ N / หัวข้อย่อย) ก่อน chunk
-> chunk จะไม่ข้ามหัวข้อ ทำให้แต่ละ chunk มีบริบทเดียว + ได้ metadata หัวข้อฟรี"""
import re

from .clean import join_lines

RE_CHAPTER = re.compile(r"^บทที่ (\d+)$")
# หัวข้อย่อยแบบ "ชื่อไทย (English title)" เช่น "ทฤษฎีสามเหลี่ยมความรัก (Triangular theory of love)"
RE_SUBHEAD = re.compile(r"^[฀-๿]+ \([A-Za-z][A-Za-z ,\-’'.]+\)$")


def _is_subheading(line, extra, prev_blank):
    # หัวข้อจริงต้องขึ้นย่อหน้าใหม่ (บรรทัดก่อนหน้าว่าง) — กันบรรทัดเนื้อหาที่บังเอิญลงท้ายด้วย "(English)"
    return line in extra or (prev_blank and len(line) < 90 and RE_SUBHEAD.match(line))


def split_chapters(pages_lines, source) -> list:
    """pages_lines: [(page_no, [lines])] -> sections [{chapter, chapter_title, section_title, category, pages, paragraphs}]"""
    keep = source.get("keep_chapters")
    sections = []

    if keep is None:  # เอกสารไม่มีโครงสร้างบท -> 1 หน้า = 1 section
        for page, lines in pages_lines:
            paras = join_lines(lines)
            if paras:
                sections.append({"chapter": None, "chapter_title": None, "section_title": None,
                                 "category": source.get("default_category", "general"), "pages": [page], "paragraphs": paras})
        return sections

    for extra in source.get("extra_sections", []):
        lo, hi = extra["pages"]
        lines = [l for p, ls in pages_lines if lo <= p <= hi for l in ls]
        sections.append({"chapter": 0, "chapter_title": extra["title"], "section_title": extra["title"],
                         "category": extra["category"], "pages": list(range(lo, hi + 1)), "paragraphs": join_lines(lines)})

    chapter, chapter_title, cur = None, None, None
    expect_title, prev_blank = False, True

    def flush():
        if cur and cur["_lines"]:
            cur["paragraphs"] = join_lines(cur.pop("_lines"))
            if cur["paragraphs"]:
                sections.append(cur)

    for page, lines in pages_lines:
        for line in lines:
            was_blank, prev_blank = prev_blank, not line
            if line in source.get("stop_headings", []) and chapter:
                flush()
                return sections
            m = RE_CHAPTER.match(line)
            if m:
                flush()
                chapter, chapter_title, cur, expect_title = int(m.group(1)), None, None, True
                continue
            if chapter is None or chapter not in keep:
                continue
            if expect_title and line:
                chapter_title, expect_title = line, False
                cur = {"chapter": chapter, "chapter_title": chapter_title, "section_title": chapter_title,
                       "category": keep[chapter], "pages": [page], "_lines": []}
                continue
            if line and _is_subheading(line, source.get("subheadings", []), was_blank):
                flush()
                cur = {"chapter": chapter, "chapter_title": chapter_title, "section_title": line,
                       "category": keep[chapter], "pages": [page], "_lines": []}
                continue
            if cur is not None:
                if page not in cur["pages"]:
                    cur["pages"].append(page)
                cur["_lines"].append(line)
    flush()
    return sections


def merge_small(sections, min_words, count_words) -> list:
    """section ที่สั้นกว่า min_words (เช่น "คำสำคัญ") รวมเข้ากับ section ถัดไปในบทเดียวกัน
    -> ไม่เกิด chunk จิ๋วที่ไม่มีบริบทพอให้ retrieval"""
    out, carry = [], None
    for sec in sections:
        if carry and carry["chapter"] == sec["chapter"]:
            sec = {**sec, "section_title": f"{carry['section_title']} / {sec['section_title']}",
                   "pages": sorted(set(carry["pages"] + sec["pages"])),
                   "paragraphs": [carry["section_title"]] + carry["paragraphs"] + [sec["section_title"]] + sec["paragraphs"]}
        elif carry:
            out.append(carry)
        carry = None
        if sum(count_words(p) for p in sec["paragraphs"]) < min_words:
            carry = sec
        else:
            out.append(sec)
    if carry:
        out.append(carry)
    return out
