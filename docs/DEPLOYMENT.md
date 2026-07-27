# KMC IRS — Production Deployment Guide

## Pre-deploy checklist

- [ ] `DEBUG=False` in `.env`
- [ ] Strong unique `SECRET_KEY` set
- [ ] `ALLOWED_HOSTS` includes production hostname(s)
- [ ] `DATABASE_URL` points to production PostgreSQL
- [ ] `KEYCLOAK_SERVER_URL` and client secrets configured
- [ ] `IRS_BASE_URL` matches public HTTPS URL
- [ ] SMTP / email settings tested (`python manage.py test_email`)
- [ ] `python manage.py migrate` run on production DB
- [ ] `python manage.py collectstatic --noinput` run
- [ ] **Do not** run `seed_data` in production
- [ ] Media directory writable and backed up
- [ ] Reverse proxy serves `/static/` and `/media/` (Django does not serve media when `DEBUG=False`)

---

## Environment variables (production)

```env
DEBUG=False
SECRET_KEY=<long-random-string>
ALLOWED_HOSTS=irs.kiiramotors.com,irs.internal.kmc.ug
DATABASE_URL=postgres://user:password@db-host:5432/irs
KEYCLOAK_SERVER_URL=https://keycloak.example.com
KEYCLOAK_REALM=kmc
KEYCLOAK_CLIENT_ID=irs
KEYCLOAK_CLIENT_SECRET=<secret>
KEYCLOAK_ADMIN_CLIENT_ID=irs
KEYCLOAK_ADMIN_CLIENT_SECRET=<secret>
IRS_BASE_URL=https://irs.kiiramotors.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=incidents@kiiramotors.com
EMAIL_HOST_PASSWORD=<secret>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=incidents@kiiramotors.com
INCIDENT_FORM_REFERENCE=KMC.DQHSE.02/26-FM005
SECURE_SSL_REDIRECT=True
```

Optional: `SECURE_HSTS_SECONDS`, `SECURE_HSTS_PRELOAD`, signature URLs.

---

## Deploy steps

### 1. Server preparation

```powershell
# Linux example
sudo apt update && sudo apt install python3.11 python3.11-venv postgresql-client nginx
```

Create app user, app directory, and PostgreSQL database.

### 2. Application setup

```powershell
cd /opt/kmc-irs
python3.11 -m venv .venv
source .venv/bin/activate   # Linux
pip install -r requirements.txt gunicorn
cp .env.example .env        # edit for production
python manage.py migrate
python manage.py collectstatic --noinput
```

### 3. Run with Gunicorn (systemd example)

```ini
[Unit]
Description=KMC Incident Reporting System
After=network.target

[Service]
User=irs
Group=irs
WorkingDirectory=/opt/kmc-irs
EnvironmentFile=/opt/kmc-irs/.env
ExecStart=/opt/kmc-irs/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Nginx reverse proxy

- Terminate TLS at Nginx
- Proxy pass to Gunicorn on `127.0.0.1:8000`
- Serve `/static/` from `staticfiles/`
- Serve `/media/` from `media/` (restrict access if needed)
- Set `client_max_body_size` ≥ 55M (10 × 5 MB photos)

### 5. Keycloak

- Redirect URI: `{IRS_BASE_URL}/oidc/callback/`
- Assign realm roles: `irs-admin`, `irs-ceo` as needed
- User `signature` attribute = URL to signature image

### 6. Post-deploy smoke test

1. SSO login
2. Create and submit test incident (UAT account)
3. Verify → approve workflow
4. Download closed PDF
5. Export CSV from History
6. Confirm email notifications arrive

---

## What not to deploy

Exclude from the production server copy:

| Item | Reason |
|------|--------|
| `.venv/`, `venv/` | Recreate on server |
| `.env` | Create separately on server (never commit) |
| `db.sqlite3` | Dev database |
| `test_media/`, `.coverage`, `htmlcov/` | Test artefacts |
| `__pycache__/`, `*.pyc` | Build artefacts |
| `_template.zip`, `_template.docx` | Dev templates |
| `scripts/build_presentation.py` | Dev tooling |
| `docs/*.pptx`, `docs/slide_content.txt` | Presentation assets |
| `requirements-dev.txt` | Dev-only (install on CI/dev machines) |

Keep on server: `requirements.txt`, `static/`, `templates/`, app code, `staticfiles/` after collectstatic.

---

## Running tests (before deploy)

```powershell
cd kmc-irs
.venv\Scripts\activate
pip install -r requirements-dev.txt

# Run all tests
python manage.py test incidents accounts --settings=config.settings_test

# Run with coverage (must meet 80% threshold)
python -m coverage run --source=accounts,incidents manage.py test incidents accounts --settings=config.settings_test
python -m coverage report
python -m coverage report --fail-under=80
```

Tests use in-memory SQLite — no PostgreSQL required for the test run.

---

## Security notes

- All incident views require login; object access checked via `user_can_view_incident`
- Drafts hidden from all users except reporter
- Workflow actions validated in service layer (role + status checks)
- Photo uploads: type, size, and Pillow content validation
- CSRF enabled on all POST forms
- Production settings enforce HTTPS cookies, HSTS, and secure headers when `DEBUG=False`
- Default dev `SECRET_KEY` blocked when `DEBUG=False`

---

## Rollback

1. Stop Gunicorn service
2. Restore previous code release
3. Restore DB backup if migrations were applied
4. Restart service

---

## Support contacts

- Application: Production IT
- Keycloak / SSO: Identity team
- Database: DBA team
