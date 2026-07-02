# Incident Reporting System (IRS)

A Django web app for plant-wide incident reporting. Employees log in through **Keycloak**, submit reports with a typed location, choose who verifies and approves, and closed cases export to PDF with signatures.

Works on phones and desktop browsers.

---

## Quick start (local development without Keycloak)

For development only, you can run without Keycloak using local demo accounts:

```powershell
cd kmc-irs
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env

python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open **http://127.0.0.1:8000** and log in with a demo account (below).

---

## Production setup (Keycloak)

1. Copy `.env.example` to `.env` and set:

```
KEYCLOAK_SERVER_URL=https://your-keycloak-server
KEYCLOAK_REALM=kmc
KEYCLOAK_CLIENT_ID=irs
KEYCLOAK_CLIENT_SECRET=...
KEYCLOAK_ADMIN_CLIENT_ID=irs
KEYCLOAK_ADMIN_CLIENT_SECRET=...
IRS_BASE_URL=https://irs.your-plant.example
```

2. In Keycloak, configure the client redirect URI: `{IRS_BASE_URL}/oidc/callback/`

3. Assign realm or client roles for elevated access:
   - `irs-admin` or `admin` → Admin (plant-wide dashboard + analytics)
   - `irs-ceo` or `ceo` → CEO (plant-wide dashboard + analytics)
   - Everyone else → Employee (can submit reports; sees only incidents they reported, verified, or approved)

4. Configure signature storage (when ready):

```
SIGNATURE_BASE_URL=https://your-signature-service/
SIGNATURE_PATH_TEMPLATE={keycloak_id}.png
```

5. Run migrations and start the app.

---

## Demo accounts (local dev only)

Created by `python manage.py seed_data` when Keycloak is **not** configured:

| Username | Password | Notes |
|----------|----------|-------|
| `worker1` | `demo123` | Submits reports |
| `supervisor_tfa` | `demo123` | Use as verifier in search |
| `manager_tfa` | `demo123` | Use as approver in search |
| `ceo` | `demo123` | Plant-wide access |
| `admin` | `admin123` | Plant-wide access |

Employee search falls back to these local users when Keycloak is unavailable.

---

## How the workflow works

```
Draft → Pending verification → Pending approval → Closed
          ↓ reject              ↓ reject
     Returned to reporter   Returned to verifier → forward → Returned to reporter
```

1. **Reporter** fills the form, types the **scene location** (max 70 characters), searches and selects a **verifier**, then submits.
2. **Verifier** reviews, assigns **severity**, searches and selects an **approver**, then verifies — or rejects back to the reporter.
3. **Approver** approves and closes — or rejects back to the verifier.

**Rules**

- Reporter, verifier, and approver must always be **three different people**.
- On resubmit or re-verify after a return, the previous verifier/approver is pre-filled but **can be changed**.
- **Severity** is set by the verifier, not the reporter.
- **1–10 photos** (5 MB each, JPEG/PNG/WEBP), at least **1 witness**, submit within **30 minutes** or provide a late reason.
- **Signatures** are fetched when submit / verify / approve happen; if none is available, the printed name is shown instead.

---

## Who sees what

| Role | Dashboard | Submit reports | Queue |
|------|-----------|----------------|-------|
| Employee | Own involved incidents only | Yes | Verify / approve items assigned to them |
| CEO | All incidents + analytics | Yes | As assigned |
| Admin | All incidents + analytics | No | — |

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `KEYCLOAK_*` | SSO login and employee search |
| `SIGNATURE_BASE_URL` | Where employee signature images are stored |
| `SIGNATURE_PATH_TEMPLATE` | Path pattern, default `{keycloak_id}.png` |
| `IRS_BASE_URL` | Base URL in notification emails |
| `DATABASE_URL` | PostgreSQL (unset → SQLite for dev) |

Application limits (in `config/settings.py`): 30-minute late threshold, 10 photos max, 20 incidents per list page.

---

## Export

- **CSV** — Dashboard → filters → Export
- **PDF** — Closed incident → Download PDF (includes full KMC logo and signatures)

---

## Project layout

```
kmc-irs/
├── config/              Settings, URLs, Keycloak OIDC
├── accounts/            User model (synced from Keycloak on login)
├── incidents/
│   ├── services/        Workflow, Keycloak search, signatures, PDF
│   ├── views.py         Pages and workflow actions
│   └── forms.py         Incident form + employee search fields
├── static/img/          Official KMC logos (icon + full)
├── templates/
└── docs/                SRS and SDD (HTML)
```

**Stack:** Python 3.11+, Django 5.x, Keycloak (OIDC), SQLite or PostgreSQL.

---

## Documentation

| Document | Location |
|----------|----------|
| Software Requirements Specification | `docs/Software_Requirements_Specification.html` |
| Software Design Document | `docs/Software_Design_Document.html` |

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Redirect loop on login | Check `IRS_BASE_URL` and Keycloak redirect URI match `/oidc/callback/` |
| Employee search empty | Verify `KEYCLOAK_ADMIN_CLIENT_*` credentials and client service-account roles |
| No signature on report | Set `SIGNATURE_BASE_URL`; missing signatures fall back to printed name |
| Cannot submit | Select verifier from search results; need at least one photo and witness |

**Reset database (dev only):**

```powershell
del db.sqlite3
python manage.py migrate
python manage.py seed_data
```

---

## License

Internal use — Kiira Motors Corporation / Production IT.
