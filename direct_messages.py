"""Private member-to-owner order enquiries and direct-message inbox.

All state is stored in ShortMint's existing SQLite/Postgres account database.
Only the conversation owner and the site owner can read or write a thread.
No payment is accepted or credits are granted by these routes.
"""
import time
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from accounts import db, user_for_request, require_owner

KINDS = {'order', 'question', 'support'}
STATUSES = {'new', 'in_progress', 'completed'}


class NewThread(BaseModel):
    kind: str = Field(max_length=20)
    subject: str = Field(min_length=3, max_length=100)
    message: str = Field(min_length=5, max_length=2000)


class Reply(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class UpdateStatus(BaseModel):
    status: str


def _clean(value):
    return value.strip()


def _can_access(thread, user):
    if not thread or (user['role'] != 'owner' and thread['user_id'] != user['id']):
        # Do not disclose existence of another member's thread.
        raise HTTPException(404, 'Conversation not found.')


def _summaries(con, user):
    role = user['role']
    col = 'owner_read_id' if role == 'owner' else 'client_read_id'
    params = [user['id']]
    where = '' if role == 'owner' else 'WHERE t.user_id=?'
    if role != 'owner':
        params.append(user['id'])
    rows = con.execute(f'''
        SELECT t.id,t.user_id,t.kind,t.subject,t.status,t.created_at,t.updated_at,
               u.username,
               (SELECT m.body FROM order_messages m WHERE m.thread_id=t.id ORDER BY m.id DESC LIMIT 1) AS preview,
               (SELECT COUNT(*) FROM order_messages m WHERE m.thread_id=t.id
                  AND m.id>t.{col} AND m.sender_id!=?) AS unread
          FROM order_threads t JOIN users u ON u.id=t.user_id
          {where} ORDER BY t.updated_at DESC,t.id DESC LIMIT 150
    ''', tuple(params)).fetchall()
    return [dict(row) for row in rows]


def install_routes(app):
    @app.get('/api/messages/threads')
    def list_threads(user=Depends(user_for_request)):
        with db() as con:
            threads = _summaries(con, user)
        return {'threads': threads, 'unread': sum(int(t['unread']) for t in threads)}

    @app.post('/api/messages/threads')
    def new_thread(body: NewThread, user=Depends(user_for_request)):
        if user['role'] == 'owner':
            raise HTTPException(403, 'Owner replies from the inbox. New enquiries are for clients.')
        kind, subject, message = body.kind, _clean(body.subject), _clean(body.message)
        if kind not in KINDS or not 3 <= len(subject) <= 100 or not 5 <= len(message) <= 2000:
            raise HTTPException(400, 'Choose a category, a subject and a message.')
        now = int(time.time())
        con = db()
        try:
            con.execute('BEGIN IMMEDIATE')
            made = con.execute('SELECT COUNT(*) AS total FROM order_threads WHERE user_id=? AND created_at>=?',
                               (user['id'], now - 86400)).fetchone()['total']
            if made >= 8:
                raise HTTPException(429, 'Daily limit reached. Reply to an existing conversation or try tomorrow.')
            row = con.execute('''INSERT INTO order_threads(user_id,kind,subject,status,created_at,updated_at)
                VALUES (?, ?, ?, 'new', ?, ?) RETURNING id''',
                (user['id'], kind, subject, now, now)).fetchone()
            tid = row['id']
            msg = con.execute('''INSERT INTO order_messages(thread_id,sender_id,body,created_at)
                VALUES (?,?,?,?) RETURNING id''', (tid, user['id'], message, now)).fetchone()
            con.execute('UPDATE order_threads SET client_read_id=? WHERE id=?',(msg['id'],tid))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {'ok': True, 'id': tid, 'message': 'Your message was sent to the owner.'}

    @app.get('/api/messages/threads/{tid}')
    def get_thread(tid: int, user=Depends(user_for_request)):
        con=db()
        try:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('''SELECT t.*,u.username FROM order_threads t
                               JOIN users u ON u.id=t.user_id WHERE t.id=?''',(tid,)).fetchone()
            _can_access(row,user)
            msgs=con.execute('''SELECT m.id,m.sender_id,m.body,m.created_at,
                CASE WHEN m.sender_id=? THEN 1 ELSE 0 END AS mine
                FROM order_messages m WHERE m.thread_id=? ORDER BY m.id DESC LIMIT 250''',
                (user['id'],tid)).fetchall()
            last_id=max((m['id'] for m in msgs),default=0)
            # Return chronological order while loading only recent history.
            msgs=list(reversed(msgs))
            col='owner_read_id' if user['role']=='owner' else 'client_read_id'
            con.execute(f'UPDATE order_threads SET {col}=? WHERE id=?', (last_id,tid))
            con.commit()
            return {'thread':dict(row),'messages':[dict(m) for m in msgs]}
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @app.post('/api/messages/threads/{tid}/reply')
    def reply(tid: int, body: Reply, user=Depends(user_for_request)):
        message=_clean(body.message)
        if not 1<=len(message)<=2000:
            raise HTTPException(400, 'Enter a message between 1 and 2,000 characters.')
        now=int(time.time())
        con=db()
        try:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM order_threads WHERE id=?',(tid,)).fetchone()
            _can_access(row,user)
            if user['role']!='owner':
                count=con.execute('''SELECT COUNT(*) AS total FROM order_messages
                    WHERE sender_id=? AND created_at>=?''',(user['id'],now-3600)).fetchone()['total']
                if count >= 30:
                    raise HTTPException(429, 'Too many messages. Please try again later.')
            msg=con.execute('''INSERT INTO order_messages(thread_id,sender_id,body,created_at)
                VALUES (?,?,?,?) RETURNING id''',(tid,user['id'],message,now)).fetchone()
            # Client replies reopen finished enquiries. First owner response starts work.
            if user['role']=='owner':
                con.execute("UPDATE order_threads SET updated_at=?,status=CASE WHEN status='new' THEN 'in_progress' ELSE status END,owner_read_id=? WHERE id=?",
                            (now,msg['id'],tid))
            else:
                con.execute("UPDATE order_threads SET updated_at=?,status=CASE WHEN status='completed' THEN 'new' ELSE status END,client_read_id=? WHERE id=?",
                            (now,msg['id'],tid))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {'ok':True}

    @app.post('/api/admin/messages/{tid}/status')
    def set_status(tid:int, body:UpdateStatus, user=Depends(require_owner)):
        if body.status not in STATUSES:
            raise HTTPException(400, 'Invalid order status.')
        with db() as con:
            result=con.execute('UPDATE order_threads SET status=?,updated_at=? WHERE id=?',(body.status,int(time.time()),tid))
            if result.rowcount!=1:
                raise HTTPException(404, 'Conversation not found.')
        return {'ok':True,'status':body.status}
