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
CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, data TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY, type TEXT, from_user TEXT, about_user TEXT, data TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS suggestions (user_id TEXT, candidate_id TEXT, score REAL, ts REAL,
  PRIMARY KEY (user_id, candidate_id));
CREATE TABLE IF NOT EXISTS reports (target_id TEXT, rf_id TEXT, count INTEGER, PRIMARY KEY (target_id, rf_id));
CREATE TABLE IF NOT EXISTS contacts (user_id TEXT PRIMARY KEY, contact TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS intros (
  id TEXT PRIMARY KEY, from_user TEXT, to_user TEXT, status TEXT, created_at REAL, decided_at REAL);
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


def create_line_user(line_user_id, display_name):
    with db() as c:
        n = c.execute("SELECT COUNT(*) FROM line_users").fetchone()[0]
        uid = f"L{n + 1:04d}"
        now = time.time()
        c.execute("INSERT INTO line_users VALUES (?,?,?,?,?,?,?)", (line_user_id, uid, display_name, "new", "{}", now, now))
    return get_line_user(line_user_id)


def set_state(line_user_id, state, data=None):
    with db() as c:
        c.execute("UPDATE line_users SET state=?, state_data=?, updated_at=? WHERE line_user_id=?",
                  (state, json.dumps(data or {}, ensure_ascii=False), time.time(), line_user_id))


def add_message(user_id, role, text, intent=None):
    with db() as c:
        c.execute("INSERT INTO messages (user_id, role, text, intent, ts) VALUES (?,?,?,?,?)", (user_id, role, text, intent, time.time()))


def recent_messages(user_id, n):
    with db() as c:
        rows = c.execute("SELECT role, text FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, n)).fetchall()
    return [dict(r) for r in reversed(rows)]


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
                    "DELETE FROM contacts WHERE user_id=?"):
            c.execute(sql, (u["user_id"],))
        c.execute("DELETE FROM line_users WHERE line_user_id=?", (line_user_id,))
