# Incident Reporting System (IRS)

A Django web app for plant-wide incident reporting at Kiira Motors Corporation. Employees log in through **Keycloak**, submit reports with a typed scene location, search and select who verifies and approves, and closed cases export to a branded PDF with signatures and audit history.

Works on phones and desktop browsers.

---

## What is built

| Area | Behaviour |
|------|-----------|
| **Authentication** | Keycloak SSO in production; local username/password demo accounts when Keycloak is not configured |
| **Roles** | Synced from Keycloak on login: `irs-admin`/`admin` → Admin, `irs-ceo`/`ceo` → CEO, everyone else → Employee |
| **Incident workflow** | Draft → Pending verification → Pending approval → Closed, with reject and return paths |
| **Sign-offs** | Reporter selects verifier at submit; verifier selects approver at verify (employee name search, top 10 results) |
| **Drafts** | Saved only when the reporter clicks **Save draft**; visible only to the reporter; reporter can delete own drafts |
| **Incident ID** | Assigned on submit: `MMYY###` (e.g. `0726001`), sequence resets each calendar month (max 999/month) |
| **Signatures** | Fetched from each person's Keycloak `signature` user attribute on submit / verify / approve; printed name if missing |
| **Notifications** | Email on submit, verify, reject, approve, forward, and close (logged in `NotificationLog`) |
| **Pages** | Dashboard (summary + recent), History (filters + CSV export), My queue (verify / approve / returned items), incident detail and form |
| **PDF export** | Closed incidents only; KMC branding, form reference, full form content, photos, timeline, signatories |
| **CSV export** | Filtered incident list from History |

**Out of scope:** automatic routing by role or location, admin reassignment of verifier/approver (verifier/approver are chosen at submit/verify and changed only via return/resubmit), or a custom `/manage/users/` UI (use Django `/admin/` for user records).

---

## Quick start (local development without Keycloak)

For development only, you can run without Keycloak using local demo accounts.

**Database:** PostgreSQL is the default. Start a local instance with Docker:

```powershell
docker compose up -d db
```

Or point `DATABASE_URL` in `.env` at an existing PostgreSQL server. Create the database once (if not using Docker):

```powershell
# After PostgreSQL is installed — adjust psql path/version if needed
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f scripts\create_postgres_db.sql
```

To use SQLite instead, remove or comment out `DATABASE_URL` in `.env`.

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

**Migrating existing SQLite data to PostgreSQL:**

```powershell
docker compose up -d db
.\scripts\migrate_to_postgres.ps1
```

The migration script sets `USE_SQLITE=1` temporarily to read from SQLite while writing to PostgreSQL.

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
INCIDENT_FORM_REFERENCE=KMC.DQHSE.02/26-FM005
```

2. In Keycloak, configure the client redirect URI: `{IRS_BASE_URL}/oidc/callback/`

3. Assign realm or client roles for elevated access:
   - `irs-admin` or `admin` → Admin (plant-wide visibility; cannot submit reports)
   - `irs-ceo` or `ceo` → CEO (plant-wide visibility; can submit reports)
   - Everyone else → Employee (can submit reports; sees only incidents they reported, verified, or approved)

4. **Signatures:** add a user attribute named `signature` on each employee in Keycloak. The value should be a full URL to their signature image (PNG or JPEG), for example:

   `https://performanceapi.kiiramotors.com/files/signatures/jane_Doe_1733921267268.jpg`

   The app reads this via the Keycloak Admin API when submit, verify, or approve happens. Optional legacy fallback if some users lack the attribute:

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

1. **Reporter** fills the form, types the **scene location** (max 70 characters), searches and selects a **verifier**, then submits. A failed submit does not create or update a draft.
2. **Verifier** reviews, assigns **severity**, searches and selects an **approver**, then verifies — or rejects back to the reporter with a comment.
3. **Approver** approves and closes — or rejects back to the verifier with a comment. The verifier can then forward the incident to the reporter for corrections.

**Rules**

- Reporter, verifier, and approver must always be **three different people**.
- On resubmit or re-verify after a return, the previous verifier/approver is pre-filled but **can be changed**.
- Resubmit clears verifier and approver signatures from the prior cycle.
- **Severity** is set by the verifier, not the reporter.
- **1–10 photos** (5 MB each, JPEG/PNG/WEBP), at least **1 witness** (one row shown by default), submit within **30 minutes** of incident time or provide a late reason.
- **Declaration** checkbox required on submit.

**Drafts**

- Use **Save draft** to store work in progress; drafts are private to the reporter.
- **Delete draft** is available on the detail and edit pages (reporter only).
- Submit when the form is complete.

---

## Who sees what

| Role | Dashboard / History | Submit reports | My queue |
|------|---------------------|----------------|----------|
| Employee | Own involved incidents only | Yes | Verify / approve / forward items assigned to them |
| CEO | All incidents + summary stats | Yes | As assigned |
| Admin | All incidents + summary stats | No | — |

Drafts are hidden from everyone except the reporter (including CEO and Admin).

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection URL (unset → SQLite fallback) |
| `USE_SQLITE` | Set to `1` to force SQLite (used by the Postgres migration script) |
| `KEYCLOAK_*` | SSO login and employee search (Admin API) |
| `IRS_BASE_URL` | Base URL in notification emails |
| `INCIDENT_FORM_REFERENCE` | Constant form code on PDF header (default `KMC.DQHSE.02/26-FM005`) |
| `SIGNATURE_BASE_URL` | Optional legacy signature file host (Keycloak attribute is primary) |
| `SIGNATURE_PATH_TEMPLATE` | Path pattern for legacy fallback, default `{keycloak_id}.png` |
| `EMAIL_BACKEND` | Django email backend (console in dev) |
| `DEFAULT_FROM_EMAIL` | Sender address for notifications |

Application limits (in `config/settings.py`): 30-minute late threshold, 10 photos max, 20 incidents per list page.

---

## Export

- **CSV** — **History** → apply filters → **Export**
- **PDF** — Closed incident detail → **Download PDF** (KMC branding, signatures, photos, timeline)

---

## Email notifications

Sent when:

- Reporter submits → verifier notified
- Verifier rejects → reporter notified
- Verifier verifies → approver notified
- Approver rejects → verifier notified
- Verifier forwards to reporter → reporter notified
- Approver closes → reporter notified

Use `python manage.py test_email` to verify SMTP settings. Failed sends are recorded in `NotificationLog` but do not block the workflow.

---

## Project layout

```
kmc-irs/
├── config/              Settings, URLs, Keycloak OIDC
├── accounts/            User model (synced from Keycloak on login)
├── incidents/
│   ├── services/        Workflow, Keycloak search, signatures, PDF, notifications, export
│   ├── views.py         Pages and workflow actions
│   └── forms.py         Incident form + employee search fields
├── static/
│   ├── css/             App styles
│   ├── js/              Form UX, employee search, history filters
│   └── img/             KMC logos (navbar, login, PDF branding)
├── templates/
├── scripts/             Postgres setup and SQLite migration helpers
└── docs/                SRS and SDD (Word; inception baseline aligned with built system)
```

**Stack:** Python 3.11+, Django 5.x, Keycloak (OIDC), PostgreSQL (SQLite fallback for dev), xhtml2pdf.

---

## Automated tests

The project includes Django unit and integration tests with a target of **at least 80% code coverage** on `accounts` and `incidents`.

```powershell
cd kmc-irs
pip install -r requirements-dev.txt

# Run tests (uses in-memory SQLite — no PostgreSQL required)
python manage.py test incidents accounts --settings=config.settings_test

# Run tests with coverage report
python -m coverage run --source=accounts,incidents manage.py test incidents accounts --settings=config.settings_test
python -m coverage report
```

Coverage configuration lives in `.coveragerc` (migrations, management commands, and test files are excluded).

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Redirect loop on login | Check `IRS_BASE_URL` and Keycloak redirect URI match `/oidc/callback/` |
| Employee search empty | Verify `KEYCLOAK_ADMIN_CLIENT_*` credentials and client service-account roles |
| No signature on report | Ensure the user has a `signature` attribute in Keycloak with a reachable image URL |
| Cannot submit | Select verifier from search results; need at least one photo and witness; complete declaration |
| Draft visible to others | Should not happen — only the reporter sees their drafts |
| PDF missing branding | Confirm `static/img/kmc-pdf-branding.png` exists |

**Reset database (dev only):**

PostgreSQL:

```powershell
docker compose down -v
docker compose up -d db
python manage.py migrate
python manage.py seed_data
```

SQLite fallback (with `DATABASE_URL` unset in `.env`):

```powershell
del db.sqlite3
python manage.py migrate
python manage.py seed_data
```

---

## License

Internal use — Kiira Motors Corporation / Production IT.
