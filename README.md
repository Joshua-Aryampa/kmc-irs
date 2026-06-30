# Incident Reporting System (IRS)

A Django web app for production-line incident reporting: workers submit reports, supervisors verify, managers approve, and closed cases can be exported to PDF.

Works on phones and desktop browsers.

---

## Quick start

```powershell
cd kmc-irs
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/macOS

python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open **http://127.0.0.1:8000** and log in (see demo accounts below).

To allow access from other devices on your network:

```powershell
python manage.py runserver 0.0.0.0:8000
```

---

## Demo accounts

Created by `python manage.py seed_data`:

| Username | Password | Role | Notes |
|----------|----------|------|-------|
| `worker1` | `demo123` | Worker | Can submit reports |
| `supervisor_tfa` | `demo123` | Supervisor | Verifies reports at Trim & Final Assembly |
| `manager_tfa` | `demo123` | Shop Floor Manager | Approves at Trim & Final Assembly |
| `supervisor_body` | `demo123` | Supervisor | Body Shop |
| `manager_body` | `demo123` | Shop Floor Manager | Body Shop |
| `director` | `demo123` | Director of Production | Plant-wide verify/approve |
| `ceo` | `demo123` | CEO | Final approver |
| `admin` | `admin123` | Admin | User management + reassignment |

**Plant locations seeded:** Trim and Final Assembly, Body Shop, Chassis Line, Paint Shop, Machine Shop, QIT.

---

## Try the full workflow

1. Log in as **`worker1`** / `demo123`
2. Click **New incident** → complete the form → add at least one witness and one photo → check the declaration → **Submit Report**
3. Log out → log in as **`supervisor_tfa`** / `demo123`
4. Open **My queue** → open the incident → choose **severity** → click **Verify**
5. Log out → log in as **`manager_tfa`** / `demo123`
6. **My queue** → open the incident → **Approve & close**
7. Open the incident again → **Download PDF**

With the default setup, notification emails print in the terminal where `runserver` is running.

---

## What the system does

- **Report** — structured incident form with Involves/classifications, witnesses, and photos
- **Route** — assigns verifier and approver automatically from reporter role and scene location
- **Review** — verifier assigns severity and verifies, or rejects with a comment
- **Approve** — approver closes the case, or rejects back to the verifier
- **Return loops** — reporter or verifier can send work back with mandatory comments
- **Track** — dashboard with filters, personal queue, and audit timeline on each incident
- **Notify** — email at key workflow steps (when SMTP is configured)
- **Export** — CSV from the dashboard; PDF for closed incidents
- **Admin** — manage users and reassign verifier/approver on open incidents

---

## Roles at a glance

| Role | Submit reports | Verify | Approve | What they see |
|------|----------------|--------|---------|---------------|
| Worker | Yes | — | — | Own reports |
| Supervisor | Yes | Yes | — | All incidents at assigned location |
| Shop Floor Manager | Yes | Yes | Yes | All incidents at assigned location |
| Director of Production | — | Yes | Yes | All incidents plant-wide |
| CEO | — | — | Yes | All incidents plant-wide |
| Admin | — | — | — | Everything + user admin |

**Who verifies and approves each report:**

| Reporter | Verifier | Approver |
|----------|----------|----------|
| Worker at location L | Supervisor at L | Shop Floor Manager at L |
| Supervisor at L | Shop Floor Manager at L | Director of Production |
| Shop Floor Manager at L | Director of Production | CEO |

Director and CEO cannot submit new reports. Reporter, verifier, and approver must always be three different people.

---

## Workflow and rules

```
Draft → Pending verification → Pending approval → Closed
          ↓ reject              ↓ reject
     Returned to reporter   Returned to verifier → forward → Returned to reporter
```

**Submission rules**

- Submit within **30 minutes** of the incident date/time, or the report is flagged **late** and requires a reason (exactly 30 minutes is still on time)
- At least **1 witness** (name + designation)
- **1–10 photos** per report, max **5 MB** each (JPEG, PNG, or WEBP)
- Reporter confirms a declaration before submit

**Review rules**

- **Severity** (Insignificant → Catastrophic) is chosen by the **verifier** when verifying — not on the reporter form
- Verifier and approver cannot edit reporter fields; they verify, approve, or reject with a required comment
- **Closed** incidents cannot be reopened
- Resubmitting after a return goes back to the same verifier and approver

**Statuses:** Draft · Pending verification · Returned to reporter · Pending approval · Returned to verifier · Closed

---

## Incident ID

Assigned on first successful submit:

```
KMC.DPN.{MM}/{DD}-{YYYY}-{SEQ}
```

Example: `KMC.DPN.06/24-2026-00001`

- Date portion comes from **submission** time
- `{SEQ}` is a 5-digit number that resets each calendar year

---

## Configuration

Copy `.env.example` to `.env`. Main variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DEBUG` | Debug mode | `True` |
| `SECRET_KEY` | Django secret | Dev placeholder — change in production |
| `ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` |
| `DATABASE_URL` | PostgreSQL connection | Unset → SQLite `db.sqlite3` |
| `EMAIL_BACKEND` | How email is sent | Console (prints to terminal) |
| `DEFAULT_FROM_EMAIL` | From address | `incidents@kiira.local` |
| `IRS_BASE_URL` | Base URL in email links | `http://127.0.0.1:8000` |
| `DEV_EMAIL_INBOX` | Optional Gmail for dev testing | Unset |

**PostgreSQL example:**

```
DATABASE_URL=postgres://irs_user:yourpassword@localhost:5432/irs
```

**Application limits** (in `config/settings.py`, not `.env`):

| Setting | Value |
|---------|-------|
| Late submission threshold | 30 minutes |
| Max photos per incident | 10 |
| Max photo size | 5 MB |

---

## Email (optional, for real inboxes in dev)

1. Set up Gmail App Password ([Google App Passwords](https://myaccount.google.com/apppasswords))
2. Add to `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your@gmail.com
DEV_EMAIL_INBOX=your@gmail.com
IRS_BASE_URL=http://127.0.0.1:8000
```

3. Re-seed users: `python manage.py seed_data` (assigns plus-tag emails like `you+supervisor-tfa@gmail.com`)
4. Test: `python manage.py test_email your@gmail.com`

**Who gets emailed:**

| Event | Recipient |
|-------|-----------|
| Submitted / resubmitted | Verifier |
| Returned to reporter | Reporter |
| Verified | Approver |
| Rejected by approver | Verifier |
| Closed | Reporter and verifier |

There are no automatic alerts by severity or classification.

---

## Export

- **CSV** — Dashboard → set filters → **Export**
- **PDF** — Open a **closed** incident → **Download PDF**

---

## Admin tasks

Log in as **`admin`** / `admin123`:

1. **Users** — http://127.0.0.1:8000/manage/users/ — create/edit users, roles, and locations  
   Only **Supervisor** and **Shop Floor Manager** need an assigned location.
2. **Reassign** — On an open incident’s detail page (Admin only) — change verifier or approver when someone is unavailable.

Django’s built-in admin is also at `/admin/` (superuser access).

**Important:** Each location needs at least one active Supervisor and Shop Floor Manager, or worker reports cannot be routed.

---

## Project layout

```
kmc-irs/
├── config/              Settings and URLs
├── accounts/            User model and login
├── incidents/
│   ├── models.py        Data models
│   ├── views.py         Pages and actions
│   ├── forms.py         Form validation
│   ├── permissions.py   Who sees what
│   └── services/        Workflow, routing, email, PDF, CSV
├── templates/           HTML pages
├── static/              CSS and JavaScript
├── docs/                SRS and SDD (HTML, open in Word)
└── manage.py
```

**Stack:** Python 3.11+, Django 5.x, SQLite or PostgreSQL, Pillow, xhtml2pdf.

---

## Documentation

| Document | Location |
|----------|----------|
| Software Requirements Specification | `docs/Software_Requirements_Specification.html` |
| Software Design Document | `docs/Software_Design_Document.html` |
| Legacy SDLC Word doc sources | `../docs/sdlc/` |

Open the HTML files in Microsoft Word and save as `.docx` if needed.

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| `No module named django` | Activate the virtual environment and run `pip install -r requirements.txt` |
| Cannot submit — routing error | Run `seed_data` or assign a Supervisor and Manager to that location |
| Role conflict on submit | Reporter, verifier, and approver must be three different users |
| Photos rejected | Use JPEG, PNG, or WEBP; max 5 MB each; max 10 per report |
| PDF missing photos | Check that files exist under the `media/` folder |
| Database locked on migrate | Stop `runserver` and close anything using `db.sqlite3` |

**Reset database (development only):**

```powershell
del db.sqlite3
python manage.py migrate
python manage.py seed_data
```

---

## Production checklist

Before deploying to a plant server:

1. Set a strong `SECRET_KEY`, `DEBUG=False`, and correct `ALLOWED_HOSTS`
2. Use PostgreSQL; back up the database and `media/` folder regularly
3. Put HTTPS in front of the app (e.g. nginx)
4. Configure a real SMTP provider and production email addresses
5. Run the app with Gunicorn/uWSGI and serve static files properly

---

## License

Internal use — Production / IT.
