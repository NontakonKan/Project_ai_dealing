"""Persistent, source-backed conversational memory; separate from matching profiles."""
import json
import re

from pipelines.llm import tasks
from pipelines.llm.context import estimate_tokens
from . import storage

RECALL = ('จำได้ไหม', 'จำได้มั้ย', 'เคยบอก', 'เคยเล่า', 'ครั้งก่อน', 'คราวก่อน', 'ก่อนหน้านี้', 'วันก่อน')
CORRECTION = ('แก้ข้อมูล', 'แก้ไข', 'เปลี่ยนเป็น', 'ไม่ใช่', 'ไม่ชอบแล้ว', 'ไม่จำกัด', 'ตอนนี้', 'เลิกแล้ว')
# These categories are not stored as conversational memories or sent to the memory model.
PRIVATE = re.compile(r'line\s*id|ไลน์|เบอร์โทร|https?://line\.me/|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|ศาสนา|มุสลิม|อิสลาม|ฮาลาล|สีผิว', re.I)


def wants_recall(text):
    return any(x in text for x in RECALL)


def safe_text(text):
    return not PRIVATE.search(text)


def _terms(text):
    text = re.sub(r'\s+', '', text.lower())
    for term in RECALL + CORRECTION:
        text = text.replace(term, '')
    return {text[i:i + 3] for i in range(max(0, len(text) - 2))}


def overlap(query, text):
    a, b = _terms(query), _terms(text)
    return len(a & b) / max(1, len(a))


def excerpt(query, text, limit=300):
    if len(text) <= limit:
        return text
    # Locate an exact query fragment in the original; do not manufacture a summary.
    terms = _terms(query)
    positions = [text.lower().find(t) for t in terms if t in text.lower()]
    start = max(0, min(positions, default=0) - 60)
    return ('…' if start else '') + text[start:start + limit] + '…[ข้อความบางส่วน]'


def refresh(uid, before_id):
    """Summarize up to 12 newest unprocessed utterances; archives remain searchable."""
    rows, checkpoint = storage.memory_pending(uid, before_id, limit=12)
    if not rows:
        return
    existing = storage.memory_facts(uid)[:12]
    safe = [r for r in rows if safe_text(r['text']) and len(r['text']) <= 2500]
    # Bound raw input while favouring newest corrections. Old details stay in the archive.
    total, bounded = 0, []
    for row in reversed(safe):
        if total + len(row['text']) > 5500:
            break
        bounded.insert(0, row)
        total += len(row['text'])
    safe = bounded
    if safe:
        changes = tasks.summarize_memory(safe, existing)
    else:
        changes = []
    storage.apply_memory(uid, changes, safe, checkpoint, rows[-1]['id'])


def context(uid, query, before_id, budget=400):
    """Current facts plus relevant original utterances; prior assistant replies are not facts."""
    facts = storage.memory_facts(uid)
    ranked = sorted(facts, key=lambda f: (overlap(query, f['summary']), f['source_id']), reverse=True)
    selected, used = [], 0
    for fact in ranked[:6]:
        entry = {'kind': 'current_memory', 'key': fact['key'], 'summary': fact['summary'],
                 'source_message_id': fact['source_id'], 'evidence': fact['evidence']}
        cost = estimate_tokens(json.dumps(entry, ensure_ascii=False))
        if used + cost <= budget:
            selected.append(entry)
            used += cost
    if wants_recall(query):
        # Search archived user text using Thai character n-grams (no whitespace tokenizer).
        candidates = storage.memory_archive(uid, before_id)
        candidates = [r for r in candidates if safe_text(r['text'])]
        candidates.sort(key=lambda r: (overlap(query, r['text']), r['id']), reverse=True)
        for row in candidates[:3]:
            if overlap(query, row['text']) < .08:
                continue
            entry = {'kind': 'historical_message_not_current_fact', 'source_message_id': row['id'],
                     'text': excerpt(query, row['text']), 'time': row['ts']}
            cost = estimate_tokens(json.dumps(entry, ensure_ascii=False))
            if used + cost <= budget:
                selected.append(entry)
                used += cost
                for reply in storage.memory_reply(uid, row['id'], before_id):
                    if not safe_text(reply['text']):
                        continue
                    entry = {'kind':'historical_assistant_not_evidence', 'source_message_id':reply['id'],
                             'text':excerpt(query, reply['text'])}
                    cost = estimate_tokens(json.dumps(entry,ensure_ascii=False))
                    if used + cost <= budget:
                        selected.append(entry)
                        used += cost
    return selected


def prepare(uid, msg, message_id, history):
    try:
        refresh(uid, message_id + 1)
    except Exception:
        # Model outage must not erase prior memory or stop the ordinary conversation.
        from . import log
        log.note('conversation memory update failed; checkpoint preserved')
    # The just-written user message is already provided as the current question.
    return context(uid, msg, message_id, budget=1000 if wants_recall(msg) else 400)
