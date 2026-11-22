"""Small DB-API compatibility layer for ShortMint's parameterized SQL.

Used only when DATABASE_URL points to an external PostgreSQL database. All
identity, credit, invitation and promo records then live outside Render.
"""
import os
import re
from functools import lru_cache


@lru_cache(maxsize=1)
def pool():
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        raise RuntimeError('DATABASE_URL is required for PostgreSQL storage.')
    return ConnectionPool(conninfo=url, min_size=0, max_size=6, timeout=15,
                          kwargs={'autocommit': True, 'row_factory': dict_row, 'prepare_threshold': None})


class Cursor:
    def __init__(self, cursor, inserted_id=None):
        self._cursor = cursor
        self.lastrowid = inserted_id

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class Connection:
    def __init__(self):
        self.raw = pool().getconn()
        self.closed = False

    def execute(self, sql, args=()):
        sql = sql.strip()
        if sql.upper() == 'BEGIN IMMEDIATE':
            sql = 'BEGIN'
        # ShortMint passes value parameters separately; never interpolate them.
        sql = sql.replace('?', '%s')
        # Preserve SQLite cursor.lastrowid semantics for two existing workflows.
        inserted_id = None
        needs_id = bool(re.match(r'INSERT\s+INTO\s+(users|purchase_requests)\b', sql, re.I))
        implicit_returning = needs_id and not re.search(r'\bRETURNING\b', sql, re.I)
        if implicit_returning:
            sql += ' RETURNING id'
        cur = self.raw.execute(sql, args)
        if implicit_returning:
            row = cur.fetchone()
            inserted_id = row['id'] if row else None
        return Cursor(cur, inserted_id)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        if not self.closed:
            self.closed = True
            pool().putconn(self.raw)

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        try:
            if typ:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()


def connect():
    return Connection()


# Schema is defined explicitly: PostgreSQL needs identity columns, not
# SQLite's implicit INTEGER PRIMARY KEY autoincrement behavior.
DDL = [
    '''CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','member')),
        credits INTEGER NOT NULL DEFAULT 0, disabled INTEGER NOT NULL DEFAULT 0,
        created_at BIGINT NOT NULL,
        google_sub TEXT UNIQUE, email TEXT, signup_ip_hash TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id),
        expires_at BIGINT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS invites (
        code TEXT PRIMARY KEY, created_at BIGINT NOT NULL,
        used_by BIGINT REFERENCES users(id), used_at BIGINT
    )''',
    '''CREATE TABLE IF NOT EXISTS credit_requests (
        id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id),
        amount INTEGER NOT NULL, message TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
        granted INTEGER, reviewed_at BIGINT, created_at BIGINT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS purchase_requests (
        id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id),
        amount INTEGER NOT NULL CHECK(amount BETWEEN 1 AND 1000), contact TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','fulfilled','rejected')),
        reviewed_at BIGINT, created_at BIGINT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS credit_log (
        id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id),
        amount INTEGER NOT NULL, reason TEXT NOT NULL, created_at BIGINT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS credit_jobs (
        job_id TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id),
        amount INTEGER NOT NULL, status TEXT NOT NULL, created_at BIGINT NOT NULL
    )''',
    'CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)',
    '''CREATE TABLE IF NOT EXISTS daily_downloads (
        job_id TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id),
        utc_date TEXT NOT NULL, cost INTEGER NOT NULL CHECK(cost BETWEEN 1 AND 3),
        status TEXT NOT NULL CHECK(status IN ('active','used','refunded')),
        created_at BIGINT NOT NULL
    )''',
    'CREATE INDEX IF NOT EXISTS idx_daily_downloads ON daily_downloads(user_id,utc_date,status)',
    '''CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY, credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 1000),
        max_uses INTEGER NOT NULL CHECK(max_uses BETWEEN 1 AND 100000),
        used_count INTEGER NOT NULL DEFAULT 0,
        expires_at BIGINT, active INTEGER NOT NULL DEFAULT 1,
        created_at BIGINT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS promo_redemptions (
        code TEXT NOT NULL REFERENCES promo_codes(code),
        user_id BIGINT NOT NULL REFERENCES users(id),
        credits INTEGER NOT NULL, redeemed_at BIGINT NOT NULL,
        PRIMARY KEY (code,user_id)
    )''',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub TEXT',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS signup_ip_hash TEXT',
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_one_signup_per_ip ON users(signup_ip_hash) WHERE role='member' AND signup_ip_hash IS NOT NULL",
    'CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub)',
    '''CREATE TABLE IF NOT EXISTS account_migration_codes (
        user_id BIGINT PRIMARY KEY REFERENCES users(id), code_hash TEXT NOT NULL,
        expires_at BIGINT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        sent_at BIGINT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS account_migration_requests (
        id BIGSERIAL PRIMARY KEY, ip_hash TEXT NOT NULL,
        email_hash TEXT NOT NULL, created_at BIGINT NOT NULL
    )''',
    'CREATE INDEX IF NOT EXISTS idx_migration_requests_ip ON account_migration_requests(ip_hash,created_at)',
    'CREATE INDEX IF NOT EXISTS idx_migration_requests_email ON account_migration_requests(email_hash,created_at)',
    '''CREATE TABLE IF NOT EXISTS account_migration_checks (
        id BIGSERIAL PRIMARY KEY, ip_hash TEXT NOT NULL,
        email_hash TEXT NOT NULL, created_at BIGINT NOT NULL
    )''',
    'CREATE INDEX IF NOT EXISTS idx_migration_checks_ip ON account_migration_checks(ip_hash,created_at)',
    'CREATE INDEX IF NOT EXISTS idx_migration_checks_email ON account_migration_checks(email_hash,created_at)',
]

DEFAULT_SETTINGS = {
    'starting_credits': '5', 'contact_email': '', 'contact_whatsapp': '',
    'invite_phone': '', 'daily_download_credits': '5',
    'public_email': '', 'public_phone': '', 'public_instagram': '',
    'public_youtube_channels': '', 'credit_prices_json': '{}'
}


def initialize():
    with connect() as con:
        # Serialize concurrent first-start DDL across app instances.
        con.execute('BEGIN')
        con.execute('SELECT pg_advisory_xact_lock(20412027)')
        for stmt in DDL:
            con.execute(stmt)
        for key, value in DEFAULT_SETTINGS.items():
            con.execute('INSERT INTO settings(name,value) VALUES (?,?) ON CONFLICT(name) DO NOTHING', (key, value))
        # Any interrupted export reserves credits but cannot finish after restart.
        con.execute("UPDATE daily_downloads SET status='refunded' WHERE status='active'")
        stranded = con.execute("SELECT job_id,user_id,amount FROM credit_jobs WHERE status='active'").fetchall()
        for entry in stranded:
            if entry['amount']:
                con.execute('UPDATE users SET credits=credits+? WHERE id=?', (entry['amount'],entry['user_id']))
                con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                            (entry['user_id'],entry['amount'],'Export interrupted; credits returned',int(__import__('time').time())))
            con.execute("UPDATE credit_jobs SET status='refunded' WHERE job_id=?", (entry['job_id'],))
