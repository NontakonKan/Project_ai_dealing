"""Structure-aware recursive chunking

ลำดับการตัด: section -> ย่อหน้า -> วลี (ช่องว่างในภาษาไทย = ขอบวลี/ประโยค)
ขนาดนับเป็น "คำ" จาก PyThaiNLP (newmm) — ภาษาไทยไม่มีช่องว่างระหว่างคำ นับตัวอักษร/ช่องว่างไม่ได้
"""
from pythainlp.tokenize import word_tokenize


def n_words(text: str) -> int:
    return sum(1 for t in word_tokenize(text, engine="newmm", keep_whitespace=False))


def _units(paragraphs, max_words):
    """แตกย่อหน้าที่ยาวเกิน max_words เป็นวลี; ย่อหน้าปกติคงไว้ทั้งก้อน"""
    for para in paragraphs:
        if n_words(para) <= max_words:
            yield para, True
        else:
            for i, phrase in enumerate(para.split(" ")):
                yield phrase, i == 0


def chunk_section(paragraphs, chunk_size=300, overlap=0.15, min_size=60) -> list:
    """คืนรายการข้อความ chunk ภายใน section เดียว (ไม่ข้าม section)"""
    overlap_words = int(chunk_size * overlap)
    chunks, cur, cur_n = [], [], 0

    for text, new_para in _units(paragraphs, chunk_size):
        n = n_words(text)
        if cur and cur_n + n > chunk_size:
            chunks.append(cur)
            tail = _tail_phrases(cur, overlap_words)
            cur, cur_n = ([(tail, False)], n_words(tail)) if tail else ([], 0)
        cur.append((text, new_para))
        cur_n += n
    if cur:
        # ก้อนท้ายเล็กเกินไป -> รวมกับก้อนก่อนหน้า
        if chunks and cur_n < min_size:
            chunks[-1].extend(u for u in cur if u not in chunks[-1])
        else:
            chunks.append(cur)
    return [_render(c) for c in chunks]


def _tail_phrases(units, overlap_words) -> str:
    """overlap: ยก "วลี" ท้ายของ chunk ก่อนหน้า (ไม่ใช่ทั้งย่อหน้า) จนได้ ~overlap_words คำ"""
    phrases = " ".join(t for t, _ in units).split(" ")
    tail, n = [], 0
    for ph in reversed(phrases):
        if n >= overlap_words:
            break
        tail.insert(0, ph)
        n += n_words(ph)
    return " ".join(tail)


def _render(units) -> str:
    out = ""
    for text, new_para in units:
        out += ("\n" if new_para and out else " " if out else "") + text
    return out.strip()
