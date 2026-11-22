"""Owner-managed promotion codes and authenticated credit redemption."""
import os
import re
import secrets
import threading
import time
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from accounts import db, require_owner, user_for_request

PROMO_TRIES = {}
PROMO_LOCK = threading.Lock()


class RedeemBody(BaseModel):
    code: str = Field(min_length=4, max_length=48)


class CreatePromo(BaseModel):
    code: str = Field(default='', max_length=32)
    credits: int = Field(ge=1, le=1000)
    max_uses: int = Field(ge=1, le=10000)
    expires_days: int = Field(default=30, ge=0, le=365)


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
