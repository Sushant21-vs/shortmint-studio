"""Public login contact is controlled by the site owner, not visitors."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import accounts
import app

HEADERS = {'X-ShortMint-Request': '1'}

@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, 'DB_FILE', tmp_path / 'db.sqlite3')
    monkeypatch.setattr(app, 'STORAGE', tmp_path / 'jobs')
    app.STORAGE.mkdir(parents=True)
    accounts.init_db()
    accounts.create_owner('owner_test', 'test_password_secret')
    with TestClient(app.app) as owner, TestClient(app.app) as visitor:
        assert owner.post('/api/auth/login', json={'username':'owner_test','password':'test_password_secret'}, headers=HEADERS).status_code == 200
        yield owner, visitor


def test_login_phone_is_public_but_owner_controls_it(clients):
    owner, visitor = clients
    state = visitor.get('/api/setup-state')
    assert state.status_code == 200
    assert state.json()['invite_phone'] == ''
    assert state.headers.get('cache-control') == 'no-store'

    r = visitor.post('/api/admin/settings', headers=HEADERS, json={'invite_phone':'+977 9812345678'})
    assert r.status_code == 401
    r = owner.post('/api/admin/settings', headers=HEADERS, json={'invite_phone':'+977 9812345678'})
    assert r.status_code == 200, r.text
    assert visitor.get('/api/setup-state').json()['invite_phone'] == '+977 9812345678'
    assert owner.get('/api/admin/overview').json()['invite_phone'] == '+977 9812345678'

    # Existing Buy Credits WhatsApp setting must NOT be silently published on login.
    assert visitor.get('/api/setup-state').json().keys() == {'owner_configured','invite_phone'}
    for invalid in ['javascript:alert(1)', '+977<script>', '9812345678', '+977 123', '+977 9999999999999999999', 12345]:
        assert owner.post('/api/admin/settings', headers=HEADERS, json={'invite_phone':invalid}).status_code == 400
    assert visitor.get('/api/setup-state').json()['invite_phone'] == '+977 9812345678'
    assert owner.post('/api/admin/settings', headers=HEADERS, json={'invite_phone':''}).status_code == 200
    assert visitor.get('/api/setup-state').json()['invite_phone'] == ''


def test_login_page_includes_contact_ui(clients):
    _, visitor = clients
    assert 'id="invite-contact-number"' in Path(app.STATIC / 'index.html').read_text(encoding='utf8')
    assert 'id="invite-phone-form"' in Path(app.STATIC / 'index.html').read_text(encoding='utf8')
    assert 'renderPublicInvitePhone' in Path(app.STATIC / 'dashboard.js').read_text(encoding='utf8')
