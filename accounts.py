"""Persistent identity, invitations, credit ledger, and role permissions for ShortMint."""
import hashlib
import json
import hmac
import os
import re
import secrets
import sqlite3
import time
import threading
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_FILE = (Path(os.environ.get('SHORTMINT_STORAGE_DIR') or str(ROOT / 'storage')).resolve() / 'shortmint.sqlite3')
DB_FILE.parent.mkdir(parents=True, exist_ok=True)
COOKIE = 'shortmint_session'
SESSION_AGE = 7 * 24 * 60 * 60
LOGIN_FAILURES = {}
LOGIN_LOCK = threading.Lock()



def db():
    if os.environ.get('DATABASE_URL', '').strip():
        from pg_storage import connect
        return connect()
    con = sqlite3.connect(DB_FILE, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=30000')
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init_db():
    if os.environ.get('REQUIRE_PERSISTENT_DB') == '1' and not os.environ.get('DATABASE_URL'):
        raise RuntimeError('Persistent DATABASE_URL is required on the hosted ShortMint server. Set up Neon before deploying v27.')
    if os.environ.get('DATABASE_URL', '').strip():
        from pg_storage import initialize
        initialize()
        return
    with db() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','member')),
            credits INTEGER NOT NULL DEFAULT 0, disabled INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invites (
            code TEXT PRIMARY KEY, created_at INTEGER NOT NULL,
            used_by INTEGER REFERENCES users(id), used_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS credit_requests (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL, message TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
            granted INTEGER, reviewed_at INTEGER, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL CHECK(amount BETWEEN 1 AND 1000),
            contact TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending'
              CHECK(status IN ('pending','fulfilled','rejected')),
            reviewed_at INTEGER,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS credit_log (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL, reason TEXT NOT NULL, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS credit_jobs (
            job_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            name TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS daily_downloads (
            job_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            utc_date TEXT NOT NULL,
            cost INTEGER NOT NULL CHECK(cost BETWEEN 1 AND 3),
            status TEXT NOT NULL CHECK(status IN ('active','used','refunded')),
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_daily_downloads ON daily_downloads(user_id,utc_date,status);
        INSERT OR IGNORE INTO settings(name,value) VALUES ('starting_credits','5');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('contact_email','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('contact_whatsapp','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('invite_phone','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('public_email','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('public_phone','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('public_instagram','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('public_youtube_channels','');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('daily_download_credits','5');
        INSERT OR IGNORE INTO settings(name,value) VALUES ('credit_prices_json','{}');
        ''')
        # Existing v26 SQLite installs gain Google IDs and promo accounting in place.
        columns = {r[1] for r in con.execute('PRAGMA table_info(users)')}
        if 'google_sub' not in columns:
            con.execute('ALTER TABLE users ADD COLUMN google_sub TEXT')
        if 'email' not in columns:
            con.execute('ALTER TABLE users ADD COLUMN email TEXT')
        con.executescript('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub);
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY, credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 1000),
            max_uses INTEGER NOT NULL CHECK(max_uses BETWEEN 1 AND 100000),
            used_count INTEGER NOT NULL DEFAULT 0,
            expires_at INTEGER, active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS promo_redemptions (
            code TEXT NOT NULL REFERENCES promo_codes(code),
            user_id INTEGER NOT NULL REFERENCES users(id),
            credits INTEGER NOT NULL, redeemed_at INTEGER NOT NULL,
            PRIMARY KEY (code,user_id)
        );
        ''')
        # If the app was closed during export, return reserved credits on restart.
        con.execute('BEGIN IMMEDIATE')
        con.execute("UPDATE daily_downloads SET status='refunded' WHERE status='active'")
        stranded = con.execute("SELECT job_id,user_id,amount FROM credit_jobs WHERE status='active'").fetchall()
        for entry in stranded:
            if entry['amount']:
                con.execute('UPDATE users SET credits=credits+? WHERE id=?', (entry['amount'], entry['user_id']))
                con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                            (entry['user_id'],entry['amount'],'Export interrupted; credits returned',int(time.time())))
            con.execute("UPDATE credit_jobs SET status='refunded' WHERE job_id=?", (entry['job_id'],))
        con.execute('COMMIT')


def hash_password(password):
    if len(password) < 10 or len(password) > 128:
        raise ValueError('Password must contain 10–128 characters.')
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 260_000)
    return salt.hex() + ':' + digest.hex()


def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split(':', 1)
        result = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 260_000)
        return hmac.compare_digest(result, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def clean_username(username):
    username = username.strip().lower()
    if not re.fullmatch('[a-z][a-z0-9_]{2,23}', username):
        raise ValueError('Use 3–24 lowercase letters, numbers, or underscores, beginning with a letter.')
    return username


def create_owner(username, password):
    username = clean_username(username)
    pwd = hash_password(password)
    con = db()
    try:
        con.execute('BEGIN IMMEDIATE')
        if con.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():
            raise ValueError('Owner account already exists.')
        con.execute("INSERT INTO users(username,password_hash,role,credits,created_at) VALUES (?,?,'owner',0,?)",
                    (username, pwd, int(time.time())))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def owner_exists():
    with db() as con:
        return bool(con.execute("SELECT 1 FROM users WHERE role='owner'").fetchone())


def public_user(row):
    return {'id':row['id'], 'username':row['username'], 'role':row['role'],
            'credits': None if row['role']=='owner' else row['credits'],
            'disabled': bool(row['disabled']), 'created_at':row['created_at'],
            'email':row['email'] if 'email' in row.keys() else None,
            'google_connected':bool(row['google_sub']) if 'google_sub' in row.keys() else False}


def user_for_request(request: Request):
    token = request.cookies.get(COOKIE,'')
    if not token:
        raise HTTPException(401,'Log in to continue.')
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db() as con:
        row = con.execute('''SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                             WHERE s.token_hash=? AND s.expires_at>?''', (digest,int(time.time()))).fetchone()
    if not row:
        raise HTTPException(401,'Your session expired. Please log in again.')
    if row['disabled']:
        raise HTTPException(403,'Your account is disabled. Contact the site owner.')
    return dict(row)


def require_owner(user=Depends(user_for_request)):
    if user['role'] != 'owner':
        raise HTTPException(403,'Only the site owner can do this.')
    return user


class Credentials(BaseModel):
    username: str
    password: str


class Register(Credentials):
    invite_code: str = Field(min_length=5, max_length=60)


class CreditRequestBody(BaseModel):
    amount: int = Field(ge=1, le=500)
    message: str = Field(default='', max_length=300)


class ReviewBody(BaseModel):
    action: str
    amount: int = Field(default=0, ge=0, le=10000)


class PurchaseBody(BaseModel):
    amount: int = Field(ge=1, le=1000)
    contact: str = Field(min_length=5, max_length=120)
    message: str = Field(default='', max_length=300)


class PurchaseReviewBody(BaseModel):
    action: str


class AdjustBody(BaseModel):
    delta: int = Field(ge=-100000, le=100000)


def _social_profile_url(value: str, platform: str) -> str:
    """Accept official HTTPS profile/channel links or a short @handle only."""
    value = value.strip()
    if not value:
        return ''
    if value.startswith('@'):
        handle = value[1:]
        if not re.fullmatch(r'[A-Za-z0-9._-]{2,70}', handle):
            raise ValueError(f'Invalid {platform} handle.')
        return ('https://www.instagram.com/' + handle + '/' if platform == 'Instagram'
                else 'https://www.youtube.com/@' + handle)
    parsed = urlsplit(value)
    allowed = {'www.instagram.com', 'instagram.com'} if platform == 'Instagram' else {
        'www.youtube.com','youtube.com','m.youtube.com'}
    if parsed.scheme != 'https' or parsed.netloc.lower() not in allowed or parsed.username or parsed.password:
        raise ValueError(f'Enter an official HTTPS {platform} profile URL (or @handle).')
    path = parsed.path.strip('/')
    if not path or len(value) > 250 or parsed.fragment:
        raise ValueError(f'Enter a valid {platform} profile/channel link.')
    if platform == 'Instagram':
        if '/' in path or path.lower() in {'reel','p','stories','explore','accounts'}:
            raise ValueError('Enter an Instagram profile link, not a Reel or post.')
    elif path.split('/')[0].lower() not in {'channel','c','user'} and not path.startswith('@'):
        raise ValueError('Enter a YouTube channel URL or @handle, not a video link.')
    if parsed.query:
        raise ValueError('Remove tracking/query parameters from the profile link.')
    return value


def _youtube_rows(value: str):
    lines=[line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) > 5:
        raise ValueError('Add up to five YouTube channels (one per line).')
    rows=[]
    for index,line in enumerate(lines,1):
        if '|' in line:
            label,url = (part.strip() for part in line.split('|',1))
        else:
            label,url = '',line
        url=_social_profile_url(url,'YouTube')
        if label and (len(label)>48 or any(ord(c)<32 for c in label)):
            raise ValueError('YouTube channel names must be under 49 characters.')
        if not label:
            label='YouTube · '+str(index)
        rows.append({'label':label,'url':url})
    return rows


def install_auth_routes(app):
    from fastapi import Response

    @app.get('/api/setup-state')
    def setup_state(response: Response):
        # This is public by design: visitors need the contact number before login.
        # Expose ONLY the explicitly configured invitation number.
        response.headers['Cache-Control'] = 'no-store'
        with db() as con:
            row = con.execute("SELECT value FROM settings WHERE name='invite_phone'").fetchone()
        return {'owner_configured':owner_exists(), 'invite_phone':row['value'] if row else ''}

    @app.post('/api/auth/login')
    def login(body: Credentials, response: Response, request: Request):
        username = body.username.strip().lower()
        address = request.client.host if request.client else 'unknown'
        now = int(time.time())
        with LOGIN_LOCK:
            failures = [t for t in LOGIN_FAILURES.get(address,[]) if t > now-600]
            LOGIN_FAILURES[address] = failures
            if len(failures) >= 8:
                raise HTTPException(429,'Too many failed logins. Try again in 10 minutes.')
        with db() as con:
            u = con.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        # Perform a hash even if username does not exist to avoid easy timing probes.
        dummy = '00000000000000000000000000000000:' + '0'*64
        correct = verify_password(body.password, u['password_hash'] if u else dummy)
        if not u or not correct:
            with LOGIN_LOCK:
                LOGIN_FAILURES.setdefault(address,[]).append(now)
            raise HTTPException(401,'Incorrect username or password.')
        with LOGIN_LOCK:
            LOGIN_FAILURES.pop(address,None)
        if u['disabled']:
            raise HTTPException(403,'Account disabled. Contact the site owner.')
        token = secrets.token_urlsafe(36)
        with db() as con:
            con.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(),u['id'],int(time.time())+SESSION_AGE))
        response.set_cookie(COOKIE,token,httponly=True,samesite='lax',secure=request.url.scheme=='https',
                            max_age=SESSION_AGE,path='/')
        return {'user':public_user(u)}

    @app.post('/api/auth/register')
    def register(body: Register):
        try:
            username = clean_username(body.username)
            pwd = hash_password(body.password)
        except ValueError as err:
            raise HTTPException(400,str(err))
        invite = body.invite_code.strip().upper()
        con = db()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT code FROM invites WHERE code=? AND used_by IS NULL', (invite,)).fetchone()
            if not row:
                raise HTTPException(400,'Invalid or already-used invitation code. Ask the owner for a new one.')
            if con.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
                raise HTTPException(409,'This username is already in use.')
            initial = int(con.execute("SELECT value FROM settings WHERE name='starting_credits'").fetchone()['value'])
            uid = con.execute("INSERT INTO users(username,password_hash,role,credits,created_at) VALUES (?,?,'member',?,?)",
                              (username,pwd,initial,int(time.time()))).lastrowid
            con.execute('UPDATE invites SET used_by=?,used_at=? WHERE code=?',(uid,int(time.time()),invite))
            con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                        (uid,initial,'Welcome credits',int(time.time())))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {'ok':True,'message':'Account created. Sign in to make Shorts.'}

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        token = request.cookies.get(COOKIE,'')
        if token:
            with db() as con:
                con.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
        response.delete_cookie(COOKIE,path='/')
        return {'ok':True}

    @app.get('/api/me')
    def me(user=Depends(user_for_request)):
        return {'user':public_user(user)}

    @app.get('/api/sidebar-contact')
    def sidebar_contact(user=Depends(user_for_request)):
        # Explicitly public-within-workspace fields. Never expose private account settings.
        with db() as con:
            vals={r['name']:r['value'] for r in con.execute(
                "SELECT name,value FROM settings WHERE name IN ('public_email','public_phone','public_instagram','public_youtube_channels')")}
        yt=[]
        try:
            yt=_youtube_rows(vals.get('public_youtube_channels',''))
        except ValueError:
            pass
        return {'email':vals.get('public_email',''), 'phone':vals.get('public_phone',''),
                'instagram':vals.get('public_instagram',''), 'youtube_channels':yt}

    @app.get('/api/credits/activity')
    def credits_activity(user=Depends(user_for_request)):
        with db() as con:
            rows = con.execute('SELECT amount,reason,created_at FROM credit_log WHERE user_id=? ORDER BY id DESC LIMIT 25',
                               (user['id'],)).fetchall()
            requests = con.execute('SELECT id,amount,message,status,granted,created_at FROM credit_requests WHERE user_id=? ORDER BY id DESC LIMIT 15',
                                   (user['id'],)).fetchall()
        return {'history':[dict(x) for x in rows], 'requests':[dict(x) for x in requests]}

    @app.post('/api/credits/request')
    def request_credits(body:CreditRequestBody,user=Depends(user_for_request)):
        if user['role']=='owner':
            raise HTTPException(400,'Your account has unlimited credits.')
        with db() as con:
            if con.execute("SELECT 1 FROM credit_requests WHERE user_id=? AND status='pending'",(user['id'],)).fetchone():
                raise HTTPException(409,'You already have a pending request. The owner can review it in Admin.')
            con.execute('INSERT INTO credit_requests(user_id,amount,message,created_at) VALUES (?,?,?,?)',
                        (user['id'],body.amount,body.message.strip(),int(time.time())))
        return {'ok':True,'message':'Credit request sent to the owner.'}

    @app.get('/api/credits/shop')
    def shop_info(user=Depends(user_for_request)):
        with db() as con:
            settings = {r['name']: r['value'] for r in con.execute(
                "SELECT name,value FROM settings WHERE name IN ('contact_email','contact_whatsapp','credit_prices_json')")}
            purchases = [dict(r) for r in con.execute(
                '''SELECT id,amount,contact,message,status,created_at,reviewed_at
                   FROM purchase_requests WHERE user_id=? ORDER BY id DESC LIMIT 30''',(user['id'],)).fetchall()]
        return {'packages':[10,25,50,100], 'email':settings.get('contact_email',''),
                'whatsapp':settings.get('contact_whatsapp',''),
                'prices':json.loads(settings.get('credit_prices_json','{}') or '{}'), 'purchases':purchases}

    @app.post('/api/credits/purchase-request')
    def request_purchase(body:PurchaseBody,user=Depends(user_for_request)):
        if user['role'] == 'owner':
            raise HTTPException(400,'Owner account already has unlimited credits.')
        contact=body.contact.strip()
        if len(contact)<5:
            raise HTTPException(400,'Enter a WhatsApp number or email where the owner can reply.')
        with db() as con:
            if con.execute("SELECT 1 FROM purchase_requests WHERE user_id=? AND status='pending'",(user['id'],)).fetchone():
                raise HTTPException(409,'You already have a pending purchase inquiry. Contact the owner or wait for a response.')
            cur=con.execute('''INSERT INTO purchase_requests(user_id,amount,contact,message,created_at) VALUES (?,?,?,?,?)''',
                            (user['id'],body.amount,contact,body.message.strip(),int(time.time())))
        return {'ok':True,'request_id':cur.lastrowid,
                'message':'Request sent to the owner. Credits are added only after the owner confirms payment.'}

    @app.get('/api/admin/overview')
    def admin_overview(user=Depends(require_owner)):
        with db() as con:
            users = con.execute('SELECT * FROM users ORDER BY created_at DESC,id DESC').fetchall()
            requests = con.execute('''SELECT cr.*,u.username FROM credit_requests cr JOIN users u ON cr.user_id=u.id
                                      ORDER BY CASE WHEN cr.status='pending' THEN 0 ELSE 1 END,cr.id DESC LIMIT 75''').fetchall()
            invites = con.execute('''SELECT i.code,i.created_at,i.used_at,u.username AS used_by
                                     FROM invites i LEFT JOIN users u ON u.id=i.used_by ORDER BY i.created_at DESC LIMIT 75''').fetchall()
            purchases = con.execute('''SELECT pr.*,u.username FROM purchase_requests pr JOIN users u ON u.id=pr.user_id
                            ORDER BY CASE WHEN pr.status='pending' THEN 0 ELSE 1 END,pr.id DESC LIMIT 100''').fetchall()
            settings = {r['name']:r['value'] for r in con.execute('SELECT name,value FROM settings')}
            welcome = int(settings.get('starting_credits','5'))
        return {'users':[public_user(u) for u in users], 'requests':[dict(r) for r in requests],
                'purchase_requests':[dict(r) for r in purchases],
                'invites':[dict(i) for i in invites], 'starting_credits':welcome,
                'contact_email':settings.get('contact_email',''),
                'contact_whatsapp':settings.get('contact_whatsapp',''),
                'invite_phone':settings.get('invite_phone',''),
                'public_email':settings.get('public_email',''),
                'public_phone':settings.get('public_phone',''),
                'public_instagram':settings.get('public_instagram',''),
                'public_youtube_channels':settings.get('public_youtube_channels',''),
                'daily_download_credits':int(settings.get('daily_download_credits','5')),
                'credit_prices':json.loads(settings.get('credit_prices_json','{}') or '{}')}

    @app.post('/api/admin/invites')
    def admin_invites(user=Depends(require_owner)):
        code = 'SM-' + secrets.token_hex(5).upper()
        with db() as con:
            con.execute('INSERT INTO invites(code,created_at) VALUES (?,?)', (code,int(time.time())))
        return {'code':code}

    @app.delete('/api/admin/invites/{code}')
    def delete_invite(code:str,user=Depends(require_owner)):
        with db() as con:
            result = con.execute('DELETE FROM invites WHERE code=? AND used_by IS NULL',(code,))
        if result.rowcount==0:
            raise HTTPException(404,'Invitation not found or already used.')
        return {'ok':True}

    @app.post('/api/admin/requests/{rid}/review')
    def review_request(rid:int,body:ReviewBody,user=Depends(require_owner)):
        if body.action not in ('approve','reject'):
            raise HTTPException(400,'Choose approve or reject.')
        if body.action=='approve' and body.amount<1:
            raise HTTPException(400,'Enter how many credits to approve.')
        con = db()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM credit_requests WHERE id=? AND status=?',(rid,'pending')).fetchone()
            if not row:
                raise HTTPException(404,'This request was already reviewed or does not exist.')
            status = 'approved' if body.action=='approve' else 'rejected'
            granted = body.amount if status=='approved' else 0
            con.execute('UPDATE credit_requests SET status=?,granted=?,reviewed_at=? WHERE id=?',
                        (status,granted,int(time.time()),rid))
            if granted:
                con.execute('UPDATE users SET credits=credits+? WHERE id=? AND role=?',(granted,row['user_id'],'member'))
                con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                            (row['user_id'],granted,'Approved credit request #'+str(rid),int(time.time())))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {'ok':True}

    @app.post('/api/admin/purchases/{rid}/review')
    def review_purchase(rid:int,body:PurchaseReviewBody,user=Depends(require_owner)):
        if body.action not in ('confirm_paid','reject'):
            raise HTTPException(400,'Choose confirm_paid or reject.')
        con=db()
        try:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute("SELECT * FROM purchase_requests WHERE id=? AND status='pending'",(rid,)).fetchone()
            if not row:
                raise HTTPException(404,'Purchase request not found or already reviewed.')
            status = 'fulfilled' if body.action=='confirm_paid' else 'rejected'
            con.execute('UPDATE purchase_requests SET status=?,reviewed_at=? WHERE id=?',
                        (status,int(time.time()),rid))
            if status=='fulfilled':
                result=con.execute("UPDATE users SET credits=credits+? WHERE id=? AND role='member'",
                                   (row['amount'],row['user_id']))
                if result.rowcount!=1:
                    raise HTTPException(404,'Member account missing.')
                con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                            (row['user_id'],row['amount'],f'Purchase request #{rid} (owner confirmed payment)',int(time.time())))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {'ok':True,'status':status}

    @app.post('/api/admin/users/{uid}/credits')
    def adjust_credits(uid:int,body:AdjustBody,user=Depends(require_owner)):
        if body.delta==0:
            raise HTTPException(400,'Choose a non-zero adjustment.')
        con=db()
        try:
            con.execute('BEGIN IMMEDIATE')
            result=con.execute('''UPDATE users SET credits=credits+? WHERE id=? AND role='member' AND credits+?>=0''',
                               (body.delta,uid,body.delta))
            if not result.rowcount:
                raise HTTPException(400,'Member not found or adjustment would make the balance negative.')
            con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                        (uid,body.delta,'Owner manually adjusted credits',int(time.time())))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {'ok':True}

    @app.post('/api/admin/users/{uid}/toggle')
    def toggle_member(uid:int,user=Depends(require_owner)):
        with db() as con:
            row=con.execute("SELECT disabled FROM users WHERE id=? AND role='member'",(uid,)).fetchone()
            if not row:
                raise HTTPException(400,'Only member accounts can be disabled.')
            disabled=0 if row['disabled'] else 1
            con.execute("UPDATE users SET disabled=? WHERE id=? AND role='member'",(disabled,uid))
            if disabled:
                con.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        return {'ok':True,'disabled':bool(disabled)}

    @app.post('/api/admin/settings')
    def save_settings(body:dict,user=Depends(require_owner)):
        valid={'starting_credits','contact_email','contact_whatsapp','daily_download_credits','invite_phone',
               'public_email','public_phone','public_instagram','public_youtube_channels', 'credit_prices_json'}
        if not body or set(body)-valid:
            raise HTTPException(400,'Invalid settings update.')
        if 'daily_download_credits' in body:
            val = body['daily_download_credits']
            if type(val) is not int or not (0 <= val <= 100):
                raise HTTPException(400,'Daily free download credits must be a whole number from 0 to 100.')
        if 'starting_credits' in body:
            val=body['starting_credits']
            if not isinstance(val,int) or isinstance(val,bool) or not 0 <= val <= 1000:
                raise HTTPException(400,'Starting credits must be a whole number from 0 to 1000.')
        if 'contact_email' in body:
            val=body['contact_email']
            if not isinstance(val,str) or len(val)>120 or (val and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',val)):
                raise HTTPException(400,'Enter a valid email address or leave blank.')
        if 'contact_whatsapp' in body:
            val=body['contact_whatsapp']
            if not isinstance(val,str) or (val and not re.fullmatch(r'\+?[0-9\s-]{7,25}',val)):
                raise HTTPException(400,'Enter a WhatsApp number with country code, or leave blank.')
            if val and not (7 <= len(re.sub(r'\D','',val)) <= 15):
                raise HTTPException(400,'WhatsApp number should contain 7–15 digits.')
        if 'invite_phone' in body:
            val=body['invite_phone']
            if not isinstance(val,str) or len(val)>28 or (val.strip() and not re.fullmatch(r'\+977(?:[ -]?\d){8,10}',val.strip())):
                raise HTTPException(400,'Enter a Nepal phone number starting +977 followed by 8–10 digits, or leave blank.')
        if 'public_email' in body:
            val=body['public_email']
            if not isinstance(val,str) or len(val)>120 or (val and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',val.strip())):
                raise HTTPException(400,'Enter a valid contact email or leave blank.')
        if 'public_phone' in body:
            val=body['public_phone']
            if not isinstance(val,str) or (val.strip() and not re.fullmatch(r'\+?[0-9 \-()]{7,28}',val.strip())) or (val.strip() and not 7<=len(re.sub(r'\D','',val))<=15):
                raise HTTPException(400,'Enter a phone number with country code, or leave blank.')
        if 'public_instagram' in body:
            val=body['public_instagram']
            if not isinstance(val,str):
                raise HTTPException(400,'Invalid Instagram profile.')
            try:
                body['public_instagram']=_social_profile_url(val,'Instagram')
            except ValueError as err:
                raise HTTPException(400,str(err))
        if 'public_youtube_channels' in body:
            val=body['public_youtube_channels']
            if not isinstance(val,str) or len(val)>1600:
                raise HTTPException(400,'YouTube channels list is too long.')
            try:
                _youtube_rows(val)
            except ValueError as err:
                raise HTTPException(400,str(err))
        if 'credit_prices_json' in body:
            value = body['credit_prices_json']
            try:
                prices = json.loads(value) if isinstance(value, str) else None
            except (ValueError, TypeError):
                prices = None
            if not isinstance(prices, dict) or set(prices) - {'10','25','50','100'} or any(
                type(v) is not int or v < 1 or v > 1000000 for v in prices.values()
            ):
                raise HTTPException(400, 'Credit pack prices must be whole NPR amounts for 10, 25, 50 or 100 credits.')
            body['credit_prices_json'] = json.dumps(prices, separators=(',',':'))
        with db() as con:
            for name, value in body.items():
                con.execute('INSERT INTO settings(name,value) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',
                            (name,str(value).strip()))
        return {'ok':True}


def reserve_credits(user, job_id, count):
    cost = 0 if user['role']=='owner' else count
    con=db()
    try:
        con.execute('BEGIN IMMEDIATE')
        if cost:
            row=con.execute("UPDATE users SET credits=credits-? WHERE id=? AND role='member' AND credits>=? AND disabled=0",
                            (cost,user['id'],cost))
            if row.rowcount==0:
                raise HTTPException(402,f'Not enough credits. You need {cost} credit(s). Request more from the owner.')
            con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                        (user['id'],-cost,'Reserved for '+str(count)+' Short(s)',int(time.time())))
        con.execute('INSERT INTO credit_jobs(job_id,user_id,amount,status,created_at) VALUES (?,?,?,?,?)',
                    (job_id,user['id'],cost,'active',int(time.time())))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return cost


def finish_credit_job(job_id, success, actual_count=None):
    con=db()
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute("SELECT user_id,amount,status FROM credit_jobs WHERE job_id=?",(job_id,)).fetchone()
        if row and row['status']=='active':
            if not success and row['amount']:
                con.execute('UPDATE users SET credits=credits+? WHERE id=?',(row['amount'],row['user_id']))
                con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                            (row['user_id'],row['amount'],'Export failed/cancelled; credits returned',int(time.time())))
            # Charge only for Shorts that were actually generated, even if fewer than requested.
            if success and actual_count is not None and row['amount'] > actual_count:
                unused = row['amount'] - actual_count
                con.execute('UPDATE users SET credits=credits+? WHERE id=?',(unused,row['user_id']))
                con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                            (row['user_id'],unused,'Unused Short credits returned',int(time.time())))
            con.execute('UPDATE credit_jobs SET status=? WHERE job_id=?',
                        ('completed' if success else 'refunded',job_id))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


init_db()


# Downloading uses a distinct *free* daily allowance. It does NOT deduct paid
# Shorts credits; limits are enforced atomically in SQLite and reset at 00:00 UTC.
def download_credit_cost(quality):
    costs = {'720': 1, '1080': 1, '1440': 2, '2160': 3}
    if quality not in costs:
        raise HTTPException(400,'Choose 720p, 1080p, 1440p or 4K.')
    return costs[quality]


def utc_day():
    return time.strftime('%Y-%m-%d', time.gmtime())


def download_quota(user):
    with db() as con:
        limit = int(con.execute("SELECT value FROM settings WHERE name='daily_download_credits'").fetchone()['value'])
        spent = con.execute("""SELECT COALESCE(SUM(cost),0) AS used FROM daily_downloads
                               WHERE user_id=? AND utc_date=? AND status IN ('active','used')""",
                            (user['id'],utc_day())).fetchone()['used']
    owner = user['role'] == 'owner'
    return {'unlimited': owner, 'limit': None if owner else limit,
            'used': 0 if owner else spent,
            'remaining': None if owner else max(0,limit-spent),
            'resets_at': '00:00 UTC', 'costs': {'720':1,'1080':1,'1440':2,'2160':3}}


def reserve_download_quota(user, job_id, quality):
    cost = download_credit_cost(quality)
    con = db()
    try:
        con.execute('BEGIN IMMEDIATE')
        day = utc_day()
        if user['role'] != 'owner':
            limit = int(con.execute("SELECT value FROM settings WHERE name='daily_download_credits'").fetchone()['value'])
            used = int(con.execute("""SELECT COALESCE(SUM(cost),0) AS total FROM daily_downloads
                                    WHERE user_id=? AND utc_date=? AND status IN ('active','used')""",
                                    (user['id'],day)).fetchone()['total'])
            if used + cost > limit:
                raise HTTPException(429,f'Daily download limit reached. You have {max(0,limit-used)} free download credits left today. Resets at 00:00 UTC.')
        con.execute("INSERT INTO daily_downloads(job_id,user_id,utc_date,cost,status,created_at) VALUES (?,?,?,?,'active',?)",
                    (job_id,user['id'],day,cost,int(time.time())))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return cost


def finish_download_quota(job_id, success):
    con = db()
    try:
        con.execute('BEGIN IMMEDIATE')
        con.execute("UPDATE daily_downloads SET status=? WHERE job_id=? AND status='active'",
                    ('used' if success else 'refunded',job_id))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
