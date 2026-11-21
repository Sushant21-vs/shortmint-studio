"""Owner-only portable SQLite backups for Render's ephemeral database.

Manual backups are a recovery option, NOT continuous durable storage. They contain
password hashes and member information: treat downloaded files as confidential.
"""
import io
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from accounts import DB_FILE, db, require_owner

MAX_BACKUP_BYTES = 12 * 1024 * 1024
REQUIRED_TABLES = ('users', 'settings', 'invites', 'credit_log', 'credit_requests', 'purchase_requests')


def _check_snapshot(snapshot, current_owner):
    try:
        table_names = {r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not all(name in table_names for name in REQUIRED_TABLES):
            raise ValueError('This is not a compatible ShortMint account backup.')
        integrity = snapshot.execute('PRAGMA integrity_check').fetchone()
        if not integrity or integrity[0] != 'ok':
            raise ValueError('Backup file is damaged.')
        owners = snapshot.execute("SELECT id,username FROM users WHERE role='owner'").fetchall()
        if len(owners) != 1 or owners[0]['username'] != current_owner:
            raise ValueError('This backup belongs to a different ShortMint owner account.')
        return owners[0]['id']
    except sqlite3.DatabaseError:
        raise ValueError('This backup file cannot be read.') from None


def install_backup_routes(app, has_active_exports=lambda: False):
    @app.get('/api/admin/data-backup')
    def download_backup(user=Depends(require_owner)):
        # SQLite online backup produces a consistent database even in WAL mode.
        with tempfile.TemporaryDirectory(prefix='sm_backup_') as td:
            destination = os.path.join(td, 'shortmint.sqlite3')
            with sqlite3.connect(destination) as copy:
                with db() as live:
                    live.backup(copy)
            with sqlite3.connect(destination) as snapshot:
                snapshot.row_factory = sqlite3.Row
                _check_snapshot(snapshot, user['username'])
            with open(destination,'rb') as file:
                content = file.read()
        if len(content) > MAX_BACKUP_BYTES:
            raise HTTPException(413,'Database too large for browser backup. Set up persistent storage.')
        date=datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')
        headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options':'nosniff',
                   'Content-Disposition':f'attachment; filename="ShortMint_private_accounts_{date}.sqlite3"'}
        return StreamingResponse(io.BytesIO(content),media_type='application/octet-stream',headers=headers)

    @app.post('/api/admin/data-restore')
    async def restore_backup(file: UploadFile = File(...), user=Depends(require_owner)):
        if has_active_exports():
            raise HTTPException(409,'Finish or cancel current exports before restoring account data.')
        payload=await file.read(MAX_BACKUP_BYTES+1)
        await file.close()
        if not payload.startswith(b'SQLite format 3\x00') or len(payload) > MAX_BACKUP_BYTES:
            raise HTTPException(400,'Upload a ShortMint SQLite backup smaller than 12 MB.')
        with tempfile.TemporaryDirectory(prefix='sm_restore_') as td:
            stage=os.path.join(td, 'restore.sqlite3')
            with open(stage,'wb') as handle: handle.write(payload)
            try:
                with sqlite3.connect(f'file:{stage}?mode=ro',uri=True) as source:
                    source.row_factory = sqlite3.Row
                    previous_owner_id = _check_snapshot(source, user['username'])
                    old_members = [dict(r) for r in source.execute("SELECT id,username,password_hash,credits,disabled,created_at FROM users WHERE role='member' ORDER BY id")]
                    old_invites = [dict(r) for r in source.execute('SELECT code,created_at,used_by,used_at FROM invites')]
                    old_logs = [dict(r) for r in source.execute('SELECT user_id,amount,reason,created_at FROM credit_log ORDER BY id')]
                    old_requests = [dict(r) for r in source.execute('SELECT user_id,amount,message,status,granted,reviewed_at,created_at FROM credit_requests ORDER BY id')]
                    old_purchases = [dict(r) for r in source.execute('SELECT user_id,amount,contact,message,status,reviewed_at,created_at FROM purchase_requests ORDER BY id')]
                    old_settings = [dict(r) for r in source.execute('SELECT name,value FROM settings')]
            except (ValueError, sqlite3.Error) as err:
                raise HTTPException(400, str(err)) from None
        # No SQL is built from untrusted backup values. The transaction rolls back on failure.
        live=db()
        try:
            live.execute('BEGIN IMMEDIATE')
            owner=live.execute("SELECT id FROM users WHERE username=? AND role='owner'",(user['username'],)).fetchone()
            if not owner:
                raise ValueError('Current owner account could not be found.')
            new_owner_id=owner['id']
            live.execute('DELETE FROM daily_downloads')
            live.execute('DELETE FROM credit_jobs')
            live.execute('DELETE FROM credit_log')
            live.execute('DELETE FROM credit_requests')
            live.execute('DELETE FROM purchase_requests')
            live.execute('DELETE FROM invites')
            live.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE role='member')")
            live.execute("DELETE FROM users WHERE role='member'")
            id_map={previous_owner_id:new_owner_id}
            for member in old_members:
                cur=live.execute('''INSERT INTO users(username,password_hash,role,credits,disabled,created_at)
                                    VALUES (?,?,'member',?,?,?)''',
                                 (member['username'],member['password_hash'],member['credits'],member['disabled'],member['created_at']))
                id_map[member['id']]=cur.lastrowid
            for invite in old_invites:
                user_id=id_map.get(invite['used_by']) if invite['used_by'] is not None else None
                if invite['used_by'] is not None and user_id is None: raise ValueError('Invalid invite member reference.')
                live.execute('INSERT INTO invites(code,created_at,used_by,used_at) VALUES (?,?,?,?)',
                             (invite['code'],invite['created_at'],user_id,invite['used_at']))
            for log in old_logs:
                live.execute('INSERT INTO credit_log(user_id,amount,reason,created_at) VALUES (?,?,?,?)',
                             (id_map[log['user_id']],log['amount'],log['reason'],log['created_at']))
            for req in old_requests:
                live.execute('''INSERT INTO credit_requests(user_id,amount,message,status,granted,reviewed_at,created_at)
                                VALUES (?,?,?,?,?,?,?)''',
                             (id_map[req['user_id']],req['amount'],req['message'],req['status'],req['granted'],req['reviewed_at'],req['created_at']))
            for req in old_purchases:
                live.execute('''INSERT INTO purchase_requests(user_id,amount,contact,message,status,reviewed_at,created_at)
                                VALUES (?,?,?,?,?,?,?)''',
                             (id_map[req['user_id']],req['amount'],req['contact'],req['message'],req['status'],req['reviewed_at'],req['created_at']))
            for setting in old_settings:
                if setting['name'] not in {'starting_credits','contact_email','contact_whatsapp','invite_phone','daily_download_credits',
                                           'public_email','public_phone','public_instagram','public_youtube_channels'}:
                    continue
                live.execute('INSERT INTO settings(name,value) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',
                             (setting['name'],setting['value']))
            live.commit()
        except (sqlite3.Error, ValueError, KeyError) as err:
            live.rollback()
            raise HTTPException(400,'Restore failed; no changes saved: '+str(err)[:180]) from None
        finally:
            live.close()
        # Passwords for members are restored (hashed), but their login sessions are not.
        return {'ok':True,'members_restored':len(old_members),'invitations_restored':len(old_invites),
                'message':'Backup restored. Members can sign in with their previous passwords.'}
