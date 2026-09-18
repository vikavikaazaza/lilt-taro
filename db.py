from pathlib import Path
import sqlite3, secrets
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
DB = BASE / 'data' / 'bot.sqlite3'
DB.parent.mkdir(parents=True, exist_ok=True)

def conn():
    c=sqlite3.connect(DB, timeout=30)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, username TEXT, name TEXT, requests INTEGER NOT NULL DEFAULT 1,
          paid_requests INTEGER NOT NULL DEFAULT 0, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
          source TEXT DEFAULT 'telegram', referrer_id INTEGER, free_granted INTEGER NOT NULL DEFAULT 1,
          total_spent INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS readings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, deck TEXT, mode TEXT, question TEXT,
          cards TEXT, answer TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payments(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, payment_id TEXT UNIQUE, amount INTEGER,
          requests INTEGER, status TEXT, email TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, event TEXT, meta TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pending(
          user_id INTEGER PRIMARY KEY, deck TEXT, mode TEXT, question TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS refs(
          code TEXT PRIMARY KEY, referrer_id INTEGER NOT NULL, used_by INTEGER UNIQUE, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS manual_subscriptions(
          user_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, granted_at TEXT NOT NULL
        );
        ''')
        # Upgrade older databases safely.
        cols={r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
        for name, definition in [('source',"TEXT DEFAULT 'telegram'"),('referrer_id','INTEGER'),('free_granted','INTEGER NOT NULL DEFAULT 1'),('total_spent','INTEGER NOT NULL DEFAULT 0')]:
            if name not in cols: c.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')

def now(): return datetime.now(timezone.utc).isoformat()

def user(tg_user, source='telegram', referrer_id=None):
    uid=tg_user.id; ts=now()
    with conn() as c:
        row=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if row:
            c.execute('UPDATE users SET username=?, name=?, last_seen=? WHERE id=?',(tg_user.username,tg_user.full_name,ts,uid))
            return c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        # Exactly one test request on first-ever registration.
        c.execute('INSERT INTO users(id,username,name,requests,paid_requests,first_seen,last_seen,source,referrer_id,free_granted) VALUES(?,?,?,?,?,?,?,?,?,1)',
                  (uid,tg_user.username,tg_user.full_name,1,0,ts,ts,source,referrer_id))
        return c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()

def get(uid):
    with conn() as c: return c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()

def manual_subscription(uid):
    with conn() as c:
        row=c.execute('SELECT enabled FROM manual_subscriptions WHERE user_id=?',(uid,)).fetchone()
        return bool(row and int(row['enabled']))

def set_manual_subscription(uid, enabled=True):
    with conn() as c:
        if enabled:
            c.execute('INSERT INTO manual_subscriptions(user_id,enabled,granted_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=1,granted_at=excluded.granted_at',(uid,1,now()))
        else:
            c.execute('UPDATE manual_subscriptions SET enabled=0,granted_at=? WHERE user_id=?',(now(),uid))

def touch(uid):
    with conn() as c: c.execute('UPDATE users SET last_seen=? WHERE id=?',(now(),uid))

def event(uid,event,meta=''):
    with conn() as c: c.execute('INSERT INTO events(user_id,event,meta,created_at) VALUES(?,?,?,?)',(uid,event,meta,now()))

def set_pending(uid,deck,mode,question):
    with conn() as c: c.execute('INSERT INTO pending(user_id,deck,mode,question,created_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET deck=excluded.deck,mode=excluded.mode,question=excluded.question,created_at=excluded.created_at',(uid,deck,mode,question,now()))

def get_pending(uid):
    with conn() as c: return c.execute('SELECT * FROM pending WHERE user_id=?',(uid,)).fetchone()

def clear_pending(uid):
    with conn() as c: c.execute('DELETE FROM pending WHERE user_id=?',(uid,))

def balance(uid):
    r=get(uid); return int(r['requests']) if r else 0

def add(uid,n):
    with conn() as c: c.execute('UPDATE users SET requests=requests+? WHERE id=?',(int(n),uid))

def consume(uid,premium=False):
    # Paid requests are consumed first; free balance remains separately visible.
    with conn() as c:
        if premium:
            cur=c.execute('UPDATE users SET paid_requests=paid_requests-1 WHERE id=? AND paid_requests>0',(uid,))
            if cur.rowcount: return True
        cur=c.execute('UPDATE users SET requests=requests-1 WHERE id=? AND requests>0',(uid,))
        return bool(cur.rowcount)

def add_paid(uid,n,amount=0):
    with conn() as c:
        c.execute('UPDATE users SET paid_requests=paid_requests+?, total_spent=total_spent+? WHERE id=?',(int(n),int(amount),uid))

def payment(uid,payment_id,amount,requests,status,email=''):
    with conn() as c:
        c.execute('INSERT OR IGNORE INTO payments(user_id,payment_id,amount,requests,status,email,created_at) VALUES(?,?,?,?,?,?,?)',(uid,payment_id,int(amount),int(requests),status,email,now()))

def payment_status(payment_id):
    with conn() as c: return c.execute('SELECT * FROM payments WHERE payment_id=?',(payment_id,)).fetchone()

def set_payment_status(payment_id,status):
    with conn() as c: c.execute('UPDATE payments SET status=? WHERE payment_id=?',(status,payment_id))

def reading(uid,deck,mode,question,cards,answer):
    with conn() as c: c.execute('INSERT INTO readings(user_id,deck,mode,question,cards,answer,created_at) VALUES(?,?,?,?,?,?,?)',(uid,deck,mode,question,cards,answer,now()))

def create_ref(uid):
    with conn() as c:
        for _ in range(10):
            code='ref'+secrets.token_hex(6)
            try:
                c.execute('INSERT INTO refs(code,referrer_id,created_at) VALUES(?,?,?)',(code,uid,now())); return code
            except sqlite3.IntegrityError: pass
    raise RuntimeError('Не удалось создать реферальную ссылку')

def use_ref(code,used_by):
    with conn() as c:
        row=c.execute('SELECT * FROM refs WHERE code=? AND used_by IS NULL',(code,)).fetchone()
        if not row or row['referrer_id']==used_by: return None
        c.execute('UPDATE refs SET used_by=? WHERE code=? AND used_by IS NULL',(used_by,code))
        if c.execute('SELECT changes()').fetchone()[0] != 1: return None
        return row['referrer_id']

def recent_readings(limit=30):
    with conn() as c: return c.execute('SELECT r.*,u.name,u.username FROM readings r LEFT JOIN users u ON u.id=r.user_id ORDER BY r.id DESC LIMIT ?',(limit,)).fetchall()

def recent_payments(limit=30):
    with conn() as c: return c.execute('SELECT p.*,u.name,u.username FROM payments p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT ?',(limit,)).fetchall()

def stats():
    with conn() as c:
        return {
          'users':c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'],
          'active':c.execute("SELECT COUNT(*) n FROM users WHERE julianday(last_seen)>=julianday('now','-7 days')").fetchone()['n'],
          'questions':c.execute('SELECT COUNT(*) n FROM readings').fetchone()['n'],
          'payments':c.execute("SELECT COUNT(*) n FROM payments WHERE status='succeeded'").fetchone()['n'],
          'revenue':c.execute("SELECT COALESCE(SUM(amount),0) n FROM payments WHERE status='succeeded'").fetchone()['n']}

def users(limit=500):
    with conn() as c: return c.execute('SELECT * FROM users ORDER BY last_seen DESC LIMIT ?',(limit,)).fetchall()

def top_payers(limit=20):
    with conn() as c: return c.execute("SELECT id,name,username,total_spent FROM users WHERE total_spent>0 ORDER BY total_spent DESC LIMIT ?",(limit,)).fetchall()

def source_stats():
    with conn() as c: return c.execute('SELECT COALESCE(source,\'telegram\') source, COUNT(*) n FROM users GROUP BY source ORDER BY n DESC').fetchall()
