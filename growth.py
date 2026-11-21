"""Verified Google account creation and owner-managed promotional credits.

All credit changes happen in database transactions; the browser may never
choose its own balance. Google account identities are keyed by verified `sub`,
not a user-provided Gmail address.
"""
import hashlib
import os
import re
import secrets
import threading
import time
from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from accounts import db, public_user, require_owner, user_for_request, COOKIE, SESSION_AGE

PROMO_TRIES = {}
PROMO_LOCK = threading.Lock()


class GoogleCredential(BaseModel):
    credential: str = Field(min_length=60, max_length=10000)
    promo_code: str = Field(default='', max_length=48)


class RedeemBody(BaseModel):
    code: str = Field(min_length=4, max_length=48)


class CreatePromo(BaseModel):
    code: str = Field(default='', max_length=32)
    credits: int = Field(ge=1, le=1000)
    max_uses: int = Field(ge=1, le=10000)
    expires_days: int = Field(default=30, ge=0, le=365)


def verify_google_identity(credential: str) -> dict:
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    if not client_id:
        raise HTTPException(503, 'Google sign-in is not configured yet. Please contact the website owner.')
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id, clock_skew_in_seconds=10)
    except Exception:
        # Never log or return ID tokens, passwords, or raw JWTs.
        raise HTTPException(401, 'Google sign-in could not be verified. Please try again.') from None
    subject = str(claims.get('sub', ''))
    email = str(claims.get('email', '')).strip().lower()
    verified = claims.get('email_verified') in (True, 'true', 'True')
    if not subject or not email or not verified or len(subject) > 255 or len(email) > 254:
        raise HTTPException(401, 'A verified Google account with an email address is required.')
    return {'sub': subject, 'email': email}


def public_google_config():
    return {'enabled': bool(os.environ.get('GOOGLE_CLIENT_ID', '').strip()),
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', '').strip()}


def _unique_google_username(email):
    stem = re.sub('[^a-z0-9_]', '', email.split('@', 1)[0].lower())
    stem = stem[:13].strip('_') or 'creator'
    if not stem[0].isalpha():
        stem = 'g' + stem
    return (stem[:13] + '_' + secrets.token_hex(4))[:24]


def _grant_google_account(sub, email):
    now = int(time.time())
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM users WHERE google_sub=?', (sub,)).fetchone()
        if row:
            return dict(row), False
        # Explicitly configured owner Gmail can sign in to existing owner.
        owner_google_email = os.environ.get('OWNER_GOOGLE_EMAIL', '').strip().lower()
        if owner_google_email and email == owner_google_email:
            owner = con.execute("SELECT * FROM users WHERE role='owner' LIMIT 1").fetchone()
            if owner:
                if owner['google_sub'] not in (None, sub):
                    raise HTTPException(409, 'Owner account is already linked to a different Google account.')
                con.execute('UPDATE users SET google_sub=?,email=? WHERE id=? AND (google_sub IS NULL OR google_sub=?)',
                            (sub,email,owner['id'],sub))
                owner = con.execute('SELECT * FROM users WHERE id=?', (owner['id'],)).fetchone()
                return dict(owner), False
        initial = int(con.execute("SELECT value FROM settings WHERE name='starting_credits'").fetchone()['value'])
        initial = max(0, min(initial, 1000))
        # A stable unique Google sub prevents duplicate welcome credits on
        # repeated logins. Conflicting simultaneous inserts have one winner.
        username = _unique_google_username(email)
        inserted = con.execute('''INSERT INTO users(username,password_hash,role,credits,created_at,google_sub,email)
                                  VALUES (?,'google-sign-in-only','member',?,?,?,?)
                                  ON CONFLICT(google_sub) DO NOTHING RETURNING id''',
                               (username,initial,now,sub,email)).fetchone()
        created = bool(inserted)
        row = con.execute('SELECT * FROM users WHERE google_sub=?', (sub,)).fetchone()
        if not row:
            raise HTTPException(503, 'Google account registration was not completed. Please retry.')
        if created:
            con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                        (row['id'],initial,'Welcome Google signup credits',now))
        return dict(row), created


def _limit_promo_attempts(uid):
    now = time.time()
    with PROMO_LOCK:
        recent = [timestamp for timestamp in PROMO_TRIES.get(uid, []) if timestamp > now - 600]
        if len(recent) >= 15:
            raise HTTPException(429, 'Too many promo attempts. Please try later.')
        recent.append(now)
        PROMO_TRIES[uid] = recent


def redeem_promo(user_id: int, entered: str):
    code = entered.strip().upper()
    if not re.fullmatch(r'[A-Z0-9_-]{4,32}', code):
        raise HTTPException(400, 'Enter a valid promotional code.')
    _limit_promo_attempts(user_id)
    now = int(time.time())
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        # Row lock protects the global max uses on PostgreSQL, even with
        # multiple app workers. SQLite uses the database write lock.
        suffix = ' FOR UPDATE' if os.environ.get('DATABASE_URL', '').strip() else ''
        promo = con.execute('SELECT * FROM promo_codes WHERE code=?' + suffix, (code,)).fetchone()
        if not promo or not promo['active'] or (promo['expires_at'] is not None and promo['expires_at'] <= now):
            raise HTTPException(400, 'This promo code is invalid or expired.')
        if promo['used_count'] >= promo['max_uses']:
            raise HTTPException(400, 'This promo code has reached its usage limit.')
        previous = con.execute('SELECT 1 FROM promo_redemptions WHERE code=? AND user_id=?', (code,user_id)).fetchone()
        if previous:
            raise HTTPException(409, 'You have already redeemed this promo code.')
        user = con.execute("SELECT role,disabled FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or user['disabled'] or user['role'] == 'owner':
            raise HTTPException(403, 'This promo code is for active member accounts.')
        con.execute('INSERT INTO promo_redemptions(code,user_id,credits,redeemed_at) VALUES (?,?,?,?)',
                    (code,user_id,promo['credits'],now))
        con.execute('UPDATE promo_codes SET used_count=used_count+1 WHERE code=?', (code,))
        con.execute('UPDATE users SET credits=credits+? WHERE id=?', (promo['credits'],user_id))
        con.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                    (user_id,promo['credits'],'Promo '+code,now))
    return promo['credits']


def install_growth_routes(app):
    @app.get('/api/auth/google-config')
    def google_config():
        return public_google_config()

    @app.post('/api/auth/google')
    def google_signin(body:GoogleCredential, response:Response, request:Request):
        identity = verify_google_identity(body.credential)
        user, created = _grant_google_account(identity['sub'], identity['email'])
        if user['disabled']:
            raise HTTPException(403, 'Account disabled. Please contact the owner.')
        promo_awarded = 0
        promo_error = None
        if body.promo_code.strip() and user['role'] == 'member':
            try:
                promo_awarded = redeem_promo(user['id'], body.promo_code)
            except HTTPException as err:
                promo_error = err.detail
        token = secrets.token_urlsafe(36)
        with db() as con:
            con.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(),user['id'],int(time.time())+SESSION_AGE))
            user = con.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
        response.set_cookie(COOKIE,token,httponly=True,samesite='lax',
                            secure=(request.url.scheme=='https'),max_age=SESSION_AGE,path='/')
        return {'user':public_user(user), 'created':created,
                'promo_awarded':promo_awarded,'promo_error':promo_error}

    @app.post('/api/credits/redeem')
    def promo_redeem(body:RedeemBody,user=Depends(user_for_request)):
        credited = redeem_promo(user['id'], body.code)
        with db() as con:
            balance=con.execute('SELECT credits FROM users WHERE id=?',(user['id'],)).fetchone()['credits']
        return {'ok':True,'credited':credited,'balance':balance}

    @app.get('/api/admin/promos')
    def list_promos(user=Depends(require_owner)):
        with db() as con:
            promos=con.execute('SELECT code,credits,max_uses,used_count,expires_at,active,created_at FROM promo_codes ORDER BY created_at DESC,code DESC LIMIT 200').fetchall()
        return {'promos':[dict(p) for p in promos]}

    @app.post('/api/admin/promos')
    def create_promo(body:CreatePromo,user=Depends(require_owner)):
        code=body.code.strip().upper() or ('SM-' + secrets.token_hex(5).upper())
        if not re.fullmatch(r'[A-Z0-9_-]{5,32}', code):
            raise HTTPException(400, 'Promo code must have 5–32 uppercase letters, numbers, - or _.')
        expires_at = int(time.time()) + body.expires_days*86400 if body.expires_days else None
        with db() as con:
            if con.execute('SELECT 1 FROM promo_codes WHERE code=?',(code,)).fetchone():
                raise HTTPException(409,'This promo code already exists.')
            con.execute('INSERT INTO promo_codes(code,credits,max_uses,expires_at,created_at) VALUES (?,?,?,?,?)',
                        (code,body.credits,body.max_uses,expires_at,int(time.time())))
        return {'ok':True,'code':code,'credits':body.credits,'max_uses':body.max_uses}

    @app.post('/api/admin/promos/{code}/disable')
    def disable_promo(code:str,user=Depends(require_owner)):
        with db() as con:
            result=con.execute('UPDATE promo_codes SET active=0 WHERE code=?',(code.strip().upper(),))
            if result.rowcount != 1:
                raise HTTPException(404,'Promo code was not found.')
        return {'ok':True}
