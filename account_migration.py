"""One-time, email-verified migration of existing Google-only ShortMint accounts.

Google sign-in stays disabled. Only the exact legacy account whose Google-verified
email is still stored, and whose password is the original migration sentinel,
can be converted. No new user, IP slot, or credits are created.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
import accounts

LOG = logging.getLogger(__name__)
CODE_LIFETIME = 10 * 60
CODE_ATTEMPTS = 5
REQUEST_MESSAGE = ('If this email belongs to an eligible previous Google account, '
                   'we will send a verification code. Check your inbox and spam folder.')
INVALID_MESSAGE = 'Invalid or expired code. Request a new code if needed.'
EMAIL_RE = re.compile(r'^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$')


class MigrationRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class MigrationConfirm(MigrationRequest):
    code: str = Field(pattern=r'^\d{6}$')
    new_password: str = Field(min_length=10, max_length=128)


def _email(raw):
    value = raw.strip().lower()
    if not EMAIL_RE.fullmatch(value):
        raise HTTPException(400, 'Enter a valid email address.')
    return value


def _secret():
    value = os.environ.get('SHORTMINT_RECOVERY_SECRET', '')
    if len(value) < 32:
        raise HTTPException(503, 'Existing-account recovery is not configured. Contact the site owner.')
    return value.encode('utf-8')


def _configured():
    secret = _secret()
    if not os.environ.get('RESEND_API_KEY', '').strip() or not os.environ.get('SHORTMINT_FROM_EMAIL','').strip():
        raise HTTPException(503, 'Existing-account recovery is not configured. Contact the site owner.')
    return secret


def _tag(key, value):
    return hmac.new(key, value.encode('utf-8'), hashlib.sha256).hexdigest()


def _google_only_user(con, email):
    # Duplicated email entries must not be guessed or merged.
    rows = con.execute("""SELECT id,username,email,google_sub,password_hash,disabled FROM users
                          WHERE LOWER(email)=? AND role='member'
                          AND google_sub IS NOT NULL AND password_hash='google-sign-in-only'
                          LIMIT 2""", (email,)).fetchall()
    if len(rows) != 1 or rows[0]['disabled']:
        return None
    return rows[0]


def _send_code(email, code):
    """Send via Resend HTTPS API (Render-compatible); never return the code to clients."""
    payload = json.dumps({
        'from': os.environ['SHORTMINT_FROM_EMAIL'],
        'to': [email],
        'subject': 'ShortMint Studio — verify your old account',
        'text': (f'Your ShortMint Studio migration code is: {code}\n\n'
                 'It expires in 10 minutes and can be used only once.\n'
                 'Enter this code on the ShortMint website to create your new password.\n\n'
                 'If you did not request this, you can ignore this message.\n')
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.resend.com/emails', data=payload, method='POST',
        headers={'Authorization':'Bearer '+os.environ['RESEND_API_KEY'].strip(),
                 'Content-Type':'application/json','User-Agent':'ShortMintStudio/41'})
    with urllib.request.urlopen(req, timeout=9) as reply:
        if reply.status not in (200,201,202):
            raise RuntimeError('Email provider did not accept the message.')


def install_migration_routes(app):
    @app.post('/api/auth/migrate/request')
    def request_migration(body: MigrationRequest, request: Request):
        secret = _configured()
        email = _email(body.email)
        ip_hash = _tag(secret, 'ip:'+accounts.signup_ip_for_request(request))
        email_hash = _tag(secret, 'email:'+email)
        now = int(time.time())
        con = accounts.db()
        recipient = None
        code = None
        token_hash = None
        uid = None
        try:
            con.execute('BEGIN IMMEDIATE')
            # Database-backed rate limits apply across app processes / restarts.
            con.execute('DELETE FROM account_migration_requests WHERE created_at<?', (now-2*86400,))
            ip_count = con.execute("""SELECT COUNT(*) AS n FROM account_migration_requests
                                      WHERE ip_hash=? AND created_at>?""", (ip_hash, now-3600)).fetchone()['n']
            email_count = con.execute("""SELECT COUNT(*) AS n FROM account_migration_requests
                                         WHERE email_hash=? AND created_at>?""", (email_hash, now-3600)).fetchone()['n']
            if ip_count >= 12 or email_count >= 3:
                con.commit()
                raise HTTPException(429, 'Too many recovery requests. Please try later.')
            con.execute('INSERT INTO account_migration_requests(ip_hash,email_hash,created_at) VALUES (?,?,?)',
                        (ip_hash,email_hash,now))
            user = _google_only_user(con,email)
            if user:
                uid = user['id']
                old = con.execute('SELECT sent_at FROM account_migration_codes WHERE user_id=?', (uid,)).fetchone()
                if not old or old['sent_at'] <= now-60:
                    code = f'{secrets.randbelow(1_000_000):06d}'
                    token_hash = _tag(secret, 'migration:'+str(uid)+':'+code)
                    con.execute("""INSERT INTO account_migration_codes(user_id,code_hash,expires_at,attempts,sent_at)
                                   VALUES (?,?,?,0,?) ON CONFLICT(user_id) DO UPDATE SET
                                   code_hash=excluded.code_hash,expires_at=excluded.expires_at,
                                   attempts=0,sent_at=excluded.sent_at""",
                                (uid,token_hash,now+CODE_LIFETIME,now))
                    recipient = email
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        if recipient:
            try:
                _send_code(recipient, code)
            except Exception:
                # No account enumeration through provider failures or response text.
                LOG.exception('ShortMint account-migration email could not be delivered')
                with accounts.db() as con:
                    con.execute('DELETE FROM account_migration_codes WHERE user_id=? AND code_hash=?',
                                (uid,token_hash))
        return {'ok': True, 'message': REQUEST_MESSAGE}

    @app.post('/api/auth/migrate/confirm')
    def confirm_migration(body: MigrationConfirm, request: Request):
        secret = _secret()
        email = _email(body.email)
        ip_hash = _tag(secret, 'ip:'+accounts.signup_ip_for_request(request))
        email_hash = _tag(secret, 'email:'+email)
        now = int(time.time())
        con = accounts.db()
        try:
            con.execute('BEGIN IMMEDIATE')
            con.execute('DELETE FROM account_migration_checks WHERE created_at<?', (now-2*86400,))
            check_count = con.execute("""SELECT COUNT(*) AS n FROM account_migration_checks
                                         WHERE (ip_hash=? OR email_hash=?) AND created_at>?""",
                                      (ip_hash,email_hash,now-3600)).fetchone()['n']
            if check_count >= 25:
                con.commit()
                raise HTTPException(429, 'Too many attempts. Please try later.')
            con.execute('INSERT INTO account_migration_checks(ip_hash,email_hash,created_at) VALUES (?,?,?)',
                        (ip_hash,email_hash,now))
            user = _google_only_user(con,email)
            if not user:
                con.commit()
                raise HTTPException(400, INVALID_MESSAGE)
            # Row lock prevents two simultaneous verifications in PostgreSQL.
            lock = ' FOR UPDATE' if os.environ.get('DATABASE_URL','').strip() else ''
            entry = con.execute("""SELECT code_hash,expires_at,attempts FROM account_migration_codes
                                   WHERE user_id=?"""+lock, (user['id'],)).fetchone()
            if not entry or entry['expires_at'] <= now or entry['attempts'] >= CODE_ATTEMPTS:
                con.commit()
                raise HTTPException(400,INVALID_MESSAGE)
            expected = _tag(secret,'migration:'+str(user['id'])+':'+body.code)
            if not hmac.compare_digest(expected,entry['code_hash']):
                con.execute('UPDATE account_migration_codes SET attempts=attempts+1 WHERE user_id=?',
                            (user['id'],))
                con.commit()
                raise HTTPException(400,INVALID_MESSAGE)
            # Hash only after the valid one-time code has been checked.
            pwd = accounts.hash_password(body.new_password)
            updated = con.execute("""UPDATE users SET password_hash=? WHERE id=?
                                     AND password_hash='google-sign-in-only' AND google_sub IS NOT NULL""",
                                  (pwd,user['id']))
            if updated.rowcount != 1:
                con.commit()
                raise HTTPException(400,INVALID_MESSAGE)
            con.execute('DELETE FROM account_migration_codes WHERE user_id=?',(user['id'],))
            con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
            con.commit()
            return {'ok':True,'username':user['username'],
                    'message':'Your existing account is ready. Sign in with your username and new password.'}
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
