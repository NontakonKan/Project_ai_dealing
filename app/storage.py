"""SQLite: ผู้ใช้ LINE, ข้อความดิบ, โปรไฟล์, events, คำแนะนำที่ส่งไปแล้ว, รายงานถึงผู้ใช้จำลอง

ข้อความดิบเก็บไว้ตรวจย้อนหลัง/ประมวลผลใหม่ และลบได้ด้วย delete_user (สิทธิ์ลบข้อมูลตาม PDPA)
"""
import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS line_users (
  line_user_id TEXT PRIMARY KEY, user_id TEXT UNIQUE, display_name TEXT, state TEXT DEFAULT 'new',
  state_data TEXT DEFAULT '{}', created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, role TEXT, text TEXT, intent TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS conversation_memory (
  user_id TEXT, key TEXT, summary TEXT, evidence TEXT, source_id INTEGER,
  PRIMARY KEY (user_id, key));
CREATE TABLE IF NOT EXISTS conversation_memory_revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, key TEXT, summary TEXT,
  evidence TEXT, source_id INTEGER, operation TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS conversation_memory_state (
  user_id TEXT PRIMARY KEY, last_message_id INTEGER);
CREATE INDEX IF NOT EXISTS messages_user_id_id ON messages(user_id, id);
CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, data TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY, type TEXT, from_user TEXT, about_user TEXT, data TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS suggestions (user_id TEXT, candidate_id TEXT, score REAL, ts REAL,
  PRIMARY KEY (user_id, candidate_id));
CREATE TABLE IF NOT EXISTS reports (target_id TEXT, rf_id TEXT, count INTEGER, PRIMARY KEY (target_id, rf_id));
CREATE TABLE IF NOT EXISTS contacts (user_id TEXT PRIMARY KEY, contact TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS intros (
  id TEXT PRIMARY KEY, from_user TEXT, to_user TEXT, status TEXT, created_at REAL, decided_at REAL);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER);
"""


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def get_line_user(line_user_id):
    with db() as c:
        r = c.execute("SELECT * FROM line_users WHERE line_user_id=?", (line_user_id,)).fetchone()
        return dict(r) | {"state_data": json.loads(r["state_data"])} if r else None


def _next_user_number(c):
    """เลขผู้ใช้ใหม่ ไม่นำเลขของคนที่ลบข้อมูลไปแล้วกลับมาใช้
    เดิมใช้ COUNT(*)+1: มี L0001, L0002 แล้ว L0001 ลบข้อมูล -> คนใหม่ได้ L0002 ซ้ำ (IntegrityError)
    และแม้ไม่ชน ก็อาจได้เลขของคนที่ลบไป ซึ่งยังถูกอ้างถึงในข้อมูลของผู้ใช้อื่น (events / intros)"""
    row = c.execute("SELECT value FROM counters WHERE name='line_user'").fetchone()
    top = c.execute("SELECT MAX(CAST(SUBSTR(user_id, 2) AS INTEGER)) FROM line_users "
                    "WHERE user_id LIKE 'L%'").fetchone()[0] or 0
    n = max(row[0] if row else 0, top) + 1
    c.execute("INSERT INTO counters VALUES ('line_user', ?) "
              "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (n,))
    return n


def create_line_user(line_user_id, display_name):
    with db() as c:
        c.execute("BEGIN IMMEDIATE")     # ผู้ใช้ใหม่ 2 คนพร้อมกันต้องไม่ได้เลขเดียวกัน
        uid = f"L{_next_user_number(c):04d}"
        now = time.time()
        c.execute("INSERT INTO line_users VALUES (?,?,?,?,?,?,?)", (line_user_id, uid, display_name, "new", "{}", now, now))
    return get_line_user(line_user_id)


def set_state(line_user_id, state, data=None):
    with db() as c:
        c.execute("UPDATE line_users SET state=?, state_data=?, updated_at=? WHERE line_user_id=?",
                  (state, json.dumps(data or {}, ensure_ascii=False), time.time(), line_user_id))


def add_message(user_id, role, text, intent=None):
    with db() as c:
        cur = c.execute("INSERT INTO messages (user_id, role, text, intent, ts) VALUES (?,?,?,?,?)", (user_id, role, text, intent, time.time()))
        return cur.lastrowid


def recent_messages(user_id, n):
    with db() as c:
        rows = c.execute("SELECT role, text FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, n)).fetchall()
    return [dict(r) for r in reversed(rows)]


def advice_history(user_id, before_id, max_tokens=800, max_age_s=None):
    """Bounded conversation context, not a retention policy.

    Keep the topic's opening question plus recent completed turns. Truncate long
    messages explicitly instead of silently dropping the latest turn. An optional
    age limit is supported, but elapsed time alone does not erase context.
    """
    import re
    from pipelines.llm.context import estimate_tokens
    from .intent import is_followup, TOPIC_RESET

    def clean(value):
        # Do not propagate contact details casually mentioned in an advice/chat turn.
        value = re.sub(r"https?://line\.me/\S+", "[ข้อมูลติดต่อถูกซ่อน]", value, flags=re.I)
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[ข้อมูลติดต่อถูกซ่อน]", value)
        value = re.sub(r"(?:line\s*(?:id)?|ไลน์(?:ไอดี)?|เบอร์โทร)\s*[:=]\s*\S+",
                       "[ข้อมูลติดต่อถูกซ่อน]", value, flags=re.I)
        return value

    def shorten(value, budget):
        if estimate_tokens(value) <= budget:
            return value
        marker = " …[ตัดบางส่วน]… "
        room = max(0, int((budget - estimate_tokens(marker) - 2) * 1.6))
        if room < 2:
            return ""
        # Keep the beginning and the end, which may contain a correction/negation.
        left = (room + 1) // 2
        return value[:left] + marker + value[-(room - left):]

    with db() as c:
        rows = c.execute(
            "SELECT role, text, intent, ts FROM messages WHERE user_id=? AND id<? "
            "ORDER BY id DESC LIMIT 24", (user_id, before_id)).fetchall()
    pairs, pending = [], []
    cutoff = time.time() - max_age_s if max_age_s is not None else None
    for row in rows:
        if row["intent"] not in {"ask_advice", "chat"} or (cutoff is not None and row["ts"] < cutoff):
            break
        if row["role"] == "bot":
            answer = re.sub(r"\[\d+\]", "", row["text"].split("\n\n📚 อ้างอิง:")[0])
            pending.insert(0, clean(answer))
        elif row["role"] == "user":
            if not pending:
                break
            pairs.insert(0, [clean(row["text"]), "\n".join(pending)])
            pending = []
            if any(c in row["text"] for c in TOPIC_RESET):
                break
            if row["intent"] == "ask_advice" and not is_followup(row["text"]):
                break

    if not pairs or max_tokens < 80:
        return []
    # Reserve room for the opening question, even when many follow-ups fill the window.
    selected = sorted(set([0] + list(range(max(0, len(pairs) - 3), len(pairs)))))
    # Each pair needs enough room to retain meaningful text for both speakers.
    while len(selected) > 1 and max_tokens // len(selected) < 160:
        selected.pop(1 if len(selected) > 2 else 0)
    history = []
    per_pair = max_tokens // len(selected)
    for i in selected:
        question, answer = pairs[i]
        available = per_pair - 20  # message overhead
        q_budget = min(estimate_tokens(question), available * 2 // 3)
        a_budget = available - q_budget
        history.extend([
            {"role": "user", "text": shorten(question, q_budget)},
            {"role": "assistant", "text": shorten(answer, a_budget)},
        ])
    return history


def save_profile(profile):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO profiles VALUES (?,?,?)",
                  (profile["user_id"], json.dumps(profile, ensure_ascii=False), time.time()))


def load_profile(user_id):
    with db() as c:
        r = c.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    return json.loads(r["data"]) if r else None


def all_profiles():
    with db() as c:
        return [json.loads(r["data"]) for r in c.execute("SELECT data FROM profiles")]


def add_event(event):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?)",
                  (event["event_id"], event["type"], event["from_user"], event["about_user"],
                   json.dumps(event, ensure_ascii=False), time.time()))


def all_events():
    with db() as c:
        return [json.loads(r["data"]) for r in c.execute("SELECT data FROM events")]


def add_suggestion(user_id, candidate_id, score):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO suggestions VALUES (?,?,?,?)", (user_id, candidate_id, score, time.time()))


def suggested(user_id):
    with db() as c:
        return {r[0] for r in c.execute("SELECT candidate_id FROM suggestions WHERE user_id=?", (user_id,))}


def add_report(target_id, rf_id):
    with db() as c:
        c.execute("INSERT INTO reports VALUES (?,?,1) ON CONFLICT(target_id, rf_id) DO UPDATE SET count=count+1", (target_id, rf_id))


def reports():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM reports")]


def set_contact(user_id, contact):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO contacts VALUES (?,?,?)", (user_id, contact, time.time()))


def get_contact(user_id):
    with db() as c:
        r = c.execute("SELECT contact FROM contacts WHERE user_id=?", (user_id,)).fetchone()
    return r[0] if r else None


def create_intro(intro_id, from_user, to_user):
    with db() as c:
        c.execute("INSERT INTO intros VALUES (?,?,?,?,?,NULL)", (intro_id, from_user, to_user, "pending", time.time()))


def get_intro(intro_id):
    with db() as c:
        r = c.execute("SELECT * FROM intros WHERE id=?", (intro_id,)).fetchone()
    return dict(r) if r else None


def find_intro(from_user, to_user):
    with db() as c:
        r = c.execute("SELECT * FROM intros WHERE from_user=? AND to_user=? ORDER BY created_at DESC LIMIT 1",
                      (from_user, to_user)).fetchone()
    return dict(r) if r else None


def decide_intro(intro_id, status):
    with db() as c:
        c.execute("UPDATE intros SET status=?, decided_at=? WHERE id=?", (status, time.time(), intro_id))


def line_id_of(user_id):
    with db() as c:
        r = c.execute("SELECT line_user_id FROM line_users WHERE user_id=?", (user_id,)).fetchone()
    return r[0] if r else None


def delete_user(line_user_id):
    """ลบข้อมูลทั้งหมดของผู้ใช้ (ข้อความ โปรไฟล์ events ที่ผู้ใช้เป็นผู้แจ้ง)"""
    u = get_line_user(line_user_id)
    if not u:
        return
    with db() as c:
        for sql in ("DELETE FROM messages WHERE user_id=?", "DELETE FROM profiles WHERE user_id=?",
                    "DELETE FROM events WHERE from_user=?", "DELETE FROM suggestions WHERE user_id=?",
                    "DELETE FROM contacts WHERE user_id=?",
                    "DELETE FROM conversation_memory WHERE user_id=?",
                    "DELETE FROM conversation_memory_revisions WHERE user_id=?",
                    "DELETE FROM conversation_memory_state WHERE user_id=?"):
            c.execute(sql, (u["user_id"],))
        c.execute("DELETE FROM line_users WHERE line_user_id=?", (line_user_id,))


def memory_facts(user_id):
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT key, summary, evidence, source_id FROM conversation_memory WHERE user_id=? ORDER BY source_id DESC",
            (user_id,))]


def memory_pending(user_id, before_id, limit=12):
    with db() as c:
        row = c.execute("SELECT last_message_id FROM conversation_memory_state WHERE user_id=?", (user_id,)).fetchone()
        checkpoint = row[0] if row else 0
        rows = c.execute(
            "SELECT id, text, ts FROM messages WHERE user_id=? AND id>? AND id<? "
            "AND role='user' AND intent IN ('chat','ask_advice') ORDER BY id DESC LIMIT ?",
            (user_id, checkpoint, before_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)], checkpoint


def apply_memory(user_id, changes, source_rows, checkpoint, through_id):
    """Validate evidence and atomically commit revisions + cursor. No model-authored SQL."""
    sources = {r['id']: r['text'] for r in source_rows}
    if not isinstance(changes, list) or len(changes) > 20:
        raise ValueError('Invalid memory changes')
    from .conversation import safe_text
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError('Invalid memory change')
        key, summary, evidence = (change.get(k) for k in ('key', 'summary', 'evidence'))
        if (not all(isinstance(x, str) and x.strip() for x in (key, summary, evidence))
                or len(key) > 80 or len(summary) > 400 or len(evidence) > 500
                or change.get('operation') not in {'set', 'delete'}
                or not isinstance(change.get('source_id'), int)
                or change['source_id'] not in sources or evidence not in sources[change['source_id']]
                or not safe_text(summary + evidence)):
            raise ValueError('Memory must cite a permitted original user message')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        state = c.execute('SELECT last_message_id FROM conversation_memory_state WHERE user_id=?', (user_id,)).fetchone()
        if (state[0] if state else 0) != checkpoint:
            return False
        for change in sorted(changes, key=lambda x: x['source_id']):
            key, summary, evidence, sid, op = (change[k] for k in ('key','summary','evidence','source_id','operation'))
            if op == 'delete':
                c.execute('DELETE FROM conversation_memory WHERE user_id=? AND key=?', (user_id,key))
            else:
                c.execute('INSERT OR REPLACE INTO conversation_memory VALUES (?,?,?,?,?)',
                          (user_id,key,summary,evidence,sid))
            c.execute('INSERT INTO conversation_memory_revisions '
                      '(user_id,key,summary,evidence,source_id,operation,ts) VALUES (?,?,?,?,?,?,?)',
                      (user_id,key,summary,evidence,sid,op,time.time()))
        c.execute('INSERT OR REPLACE INTO conversation_memory_state VALUES (?,?)', (user_id,through_id))
    return True


def memory_archive(user_id, before_id):
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,text,ts FROM messages WHERE user_id=? AND id<? "
            "AND role='user' AND intent IN ('chat','ask_advice') ORDER BY id DESC LIMIT 1000",
            (user_id,before_id))]


def memory_reply(user_id, source_id, before_id):
    """Original assistant text belonging to an archived user turn, labelled as such."""
    with db() as c:
        next_user = c.execute("SELECT MIN(id) FROM messages WHERE user_id=? AND role='user' AND id>?",
                              (user_id,source_id)).fetchone()[0]
        end = min(before_id, next_user or before_id)
        rows = c.execute("SELECT id,text,ts FROM messages WHERE user_id=? AND id>? AND id<? "
                         "AND role='bot' AND intent IN ('chat','ask_advice') ORDER BY id LIMIT 2",
                         (user_id,source_id,end)).fetchall()
    return [dict(r) for r in rows]
