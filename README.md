# Kinnatic Outreach

Internal tool for founder-led 1:1 cold outreach. Upload a CSV of prospects, pick one row and one
template, read exactly what will be sent, click Send. The server sends a single plain-text email
through one Google Workspace mailbox via the Gmail API, with a hard cap of 20 successful sends per
calendar day in the operator timezone (default `Australia/Brisbane`, set in Settings).

**What this is not**, by design:

- Not an ESP. No Resend, SendGrid, SES, Mailgun — mail leaves only through the Gmail API.
- No sequences, no queues, no scheduler. One send is one deliberate human action.
- No open tracking, click tracking, or tracking pixels.
- No `List-Unsubscribe`, `List-Unsubscribe-Post`, `List-ID` or `Precedence: bulk` headers.
- No HTML in the pitch. The body is plain text; only the Gmail account signature is HTML.

The gates are the product. Everything below exists to stop a send that should not happen.

> Read [`docs/threat-model.md`](docs/threat-model.md) before your first real send. This tool sends
> unsolicited commercial electronic messages and **does not create consent**.

---

## Stack

| Layer    | Choice                                                                        |
| -------- | ----------------------------------------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2 (sync, psycopg3), Postgres                  |
| Frontend | React 19, TypeScript, Vite, Tailwind v4, shadcn/ui, TanStack Query, React Router |
| Monorepo | Nx + npm workspaces (`apps/api`, `apps/web`)                                  |
| Email    | Gmail API over `httpx` — no `google-api-python-client`, no SMTP anywhere       |

---

## Run it

Prerequisites: Python 3.12+, Node 20+, Docker.

```bash
npm install
```

```bash
cd apps/api && docker compose up -d
```

Postgres comes up on **port 5433** (5432 is left alone for any system Postgres). The container also
creates `outreach_test` for the test suite.

```bash
cd apps/api && cp .env.example .env && cp .env.test.example .env.test
```

Fill in `SECRET_KEY` and `OUTREACH_APP_PASSWORD` — generate each with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then migrate the schema and seed the two default templates:

```bash
cd apps/api && pip install -r requirements.txt && python -m app.cli.seed
```

`seed` runs migrations (`up`) then inserts defaults. To migrate without seeding:

```bash
npm run migrate            # apply pending
npm run migrate:status     # list applied / pending
npm run migrate:down       # roll back one step
```

Start the API:

```bash
cd apps/api && uvicorn app.main:app --reload --port 8000
```

Start the UI in a second terminal:

```bash
cd apps/web && npm run dev
```

Open <http://localhost:5173> and sign in with `OUTREACH_APP_PASSWORD`.

Or run both together from the repo root:

```bash
npm run dev
```

> **Port 5173 already in use?** If you run another Vite app (for example `kinnatic/apps/frontend`),
> Vite will pick 5174 and the OAuth redirect back to the UI will land on the wrong port. Either stop
> the other server, or set `FRONTEND_URL` and `CORS_ORIGIN` in `apps/api/.env` to the port you
> actually use.

---

## Connect Gmail

Nothing can be sent until a mailbox is connected. The address you authorise becomes the `From` and
`Reply-To` for every email — Gmail forces the authenticated account as the sender, which is why
`from_email` is read from the Gmail profile and is not editable in the UI.

1. Go to the [Google Cloud console](https://console.cloud.google.com/) and create a project.
2. **APIs & Services → Library →** enable the **Gmail API**.
3. **APIs & Services → OAuth consent screen.**
   - Choose **Internal** if this is a Google Workspace account. Strongly recommended — see the
     warning below.
   - If you must use **External**, add your own Google account under **Test users**.
   - Scopes requested: `gmail.send`, `gmail.readonly`, and `gmail.settings.basic`
     (the last one reads the HTML signature on the sendAs identity).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID.**
   - Application type: **Web application** (not Desktop).
   - Authorised redirect URI, exactly:
     ```
     http://localhost:8000/auth/google/callback
     ```
     This is derived from `APP_BASE_URL`, so if you change that you must change this to match.
5. Copy the client ID and secret into `apps/api/.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
   and restart the API.
6. In the app: **Settings → Connect Gmail**. After consent you are returned to Settings and the
   mailbox address appears.

> ⚠️ **Two things to know about External + Testing mode.**
> `gmail.readonly` is a Google **Restricted** scope, so publishing an External app requires a
> security assessment. And while an External app is in **Testing**, Google expires refresh tokens
> after **7 days**, so you will have to reconnect weekly. **Internal** (Workspace) publishing has
> neither limitation.
>
> If you drop the Sync inbox feature, `gmail.send` alone is only a *Sensitive* scope and is much
> easier to publish. There is no narrower read scope that works — `gmail.metadata` cannot see
> message bodies, so it cannot support stop-word matching.

---

## Import a CSV

**Contacts → Import CSV.** Pick a file, then confirm how each header maps to a field. Only an
**email** column is required. Company and every other field are optional — a blank or unmapped
company imports the contact with no company.

Common header spellings are suggested automatically (case and punctuation are ignored); you can
override any suggestion before importing:

| Field        | Suggested headers                                                     |
| ------------ | --------------------------------------------------------------------- |
| `email`      | email, Email, Work Email, E-Mail, Business Email, Primary Email        |
| `first_name` | first_name, First Name, First, Given Name, fname                       |
| `last_name`  | last_name, Last Name, Last, Surname, Family Name, lname                |
| `company`    | company, Company Name, Organisation, Organization, Account, Employer   |
| `location`   | company_location, Company Location, location, city                     |
| `title`      | title, Job Title, Position, Role                                       |
| `hook`       | hook, angle                                                            |
| `notes`         | notes, note, comments — free text stored on the contact             |
| `contact_notes` | contact notes, contact note — a note on the contact                 |
| `company_notes` | company notes, company note — a note on the company                 |
| `source`        | source, Source URL, Lead Source, url                                 |
| *(name)*     | name, Full Name, Contact Name — split into first/last if no first/last |

Matching company names (case-insensitive) share one company row. Open **Companies** in the nav to
browse them and send to a company's contacts. A company or contact page can hold its own notes.
`company notes` and `contact notes` in a CSV create those notes; the `notes` column stays free
text on the contact.

Try it with the sample file, which deliberately exercises every outcome:

```bash
open examples/prospects.csv
```

It produces 3 valid, 1 consumer-domain warning, and 2 auto-suppressed invalid rows (one domain
publishes a null MX record, the other does not exist).

Limits: 500 rows and 2 MB per upload. Duplicates are skipped case-insensitively, both within the
file and against contacts already stored.

Every new address is validated on import:

- **`ZEROBOUNCE_API_KEY` set** → ZeroBounce.
- **Not set** → syntax check plus an MX lookup via dnspython.

Neither path ever opens an SMTP connection to a prospect's mail server — that is how a sending IP
gets blocklisted, and `tests/test_guards.py` enforces it by scanning the source.

> **What "valid" means on the free path.** The MX check validates the **domain, not the mailbox**.
> DNS carries no per-mailbox information, so `ben@yourdomain.com` and `joey@yourdomain.com` get an
> identical verdict even if only one exists. A `valid` badge means "this domain accepts mail".
>
> Only three things can confirm an individual mailbox: an SMTP probe (never done here — see above),
> a commercial validator, or sending and watching for the bounce. **Set `ZEROBOUNCE_API_KEY` if you
> need mailbox-level certainty before sending.**
>
> Nonexistent addresses are still caught, just one step later: most corporate mail (including Google
> Workspace, which rejects unknown recipients by default) hard-bounces with a `5.x.x` status, and
> **Sync inbox** then suppresses the address automatically as a permanent bounce.

`invalid` addresses are suppressed automatically. `risky` (usually a catch-all domain) is allowed
but requires ticking a confirmation box at send time. Rows the validator could not reach within the
import's time budget stay `pending` and can be validated later from the contact page.

---

## Sending

Pick a contact, choose a template, and the modal shows the byte-exact message that will go out. The
Send button is disabled while any blocker is present — but that is a courtesy, not the control. The
server re-evaluates every gate inside the sending transaction and refuses regardless of what the UI
did.

**Blockers — the send is refused**

| Code                     | Cleared by                                                       |
| ------------------------ | ---------------------------------------------------------------- |
| `gmail_not_connected`    | Connecting a mailbox in Settings                                 |
| `settings_incomplete`    | Legal company name on the settings row, and a connected From address   |
| `template_missing`       | Choosing a template that still exists                            |
| `email_invalid`          | Nothing. Invalid addresses are never sent to                     |
| `contact_suppressed`     | Nothing automatic. Only a manual removal from Suppressions        |
| `cooldown_active`        | Waiting out `COOLDOWN_DAYS` (default 14)                          |
| `daily_cap_reached`      | The next calendar day in the operator timezone                   |
| `unrendered_merge_tags`  | Filling the missing contact field, or using another template      |
| `subject_empty` / `body_empty` | Fixing the template                                        |
| `warning_not_acknowledged` | Ticking the "send anyway" box for each flagged warning          |

**Warnings — the send proceeds, but look first**

`validation_risky`, `validation_pending`, `validation_unknown` (these three require
acknowledgement), `consumer_domain`, `missing_company`, `missing_title`, `multiple_links`,
`no_source_recorded`.

### What gets appended

Every outgoing body ends with the Gmail account HTML signature (when the mailbox
grant includes `gmail.settings.basic`), the human opt-out sentence, and on its
own line a unique unsubscribe URL:

```
Hi Avery,

…

Joey
CEO, Kinnatic Pty Ltd
kinnatic.ai

If this isn't relevant, reply "no" and I won't email again.

Unsubscribe: http://localhost:8000/u/<token>
```

The pitch stays plain text. The signature is the same HTML Gmail stores under
Settings → Signature for that sendAs address — logos and links included. Edit it
in Gmail; this app only reads it. Signature links do not count toward the
`multiple_links` warning.

The unsubscribe URL can be turned off in **Settings → Unsubscribe link**. When
off, the opt-out sentence and signature still go out; only the per-contact URL
is skipped.

Both the opt-out and unsub appends are idempotent. Disconnect and reconnect
Gmail once after upgrading so the token picks up the settings scope.

Merge fields follow one rule: **an empty value leaves its `{{tag}}` in place, and a leftover tag is a
hard blocker.** A contact with no company therefore cannot receive a template that mentions
`{{company}}`, and a typo'd `{{industy}}` fails closed rather than emailing a CISO a raw template
tag.

---

## The daily cap

The cap counts successful sends per **calendar day in the operator timezone** (IANA name in
Settings; default `Australia/Brisbane`). The day rolls over at midnight in that zone.

A slot is reserved **before** the Gmail call and compensated on failure, so the app under-sends
rather than risking a double send:

| Gmail outcome                               | Slot                                        |
| ------------------------------------------- | ------------------------------------------- |
| Success                                     | Consumed                                    |
| 4xx — Gmail demonstrably never queued it    | Released, and the cooldown stamp is undone  |
| Timeout / 429 / 5xx — it may have gone out  | **Kept.** Check Gmail Sent before retrying  |

If the process dies between the send and the commit, the row stays `queued` and the Dashboard says
so. Because the RFC 822 `Message-ID` is generated and stored *before* sending, the true outcome is
recoverable:

```bash
cd apps/api && python -m app.cli.reconcile_sends
```

That searches Gmail for each stuck message and either promotes it to `sent` or, after an hour's
grace, marks it `failed` and releases the slot.

`DAILY_CAP` in `.env` only seeds the initial value; after that the Settings page is authoritative.
The server clamps whatever is stored to a hard ceiling of **50**, so a mistake there cannot lift the
cap.

---

## Replies, bounces and unsubscribes

**The public unsubscribe page** is served by the API at `/u/{token}` — no login, no JavaScript,
works with images blocked. `GET` renders a confirmation page; `POST` performs the suppression. The
split is deliberate: mail clients and corporate security gateways prefetch links in received mail,
and a GET that suppressed on sight would remove prospects who never clicked. Unknown, malformed and
already-used tokens all render the same neutral page with HTTP 200, so the endpoint cannot be used
to enumerate which tokens are real.

**Sync inbox** (Dashboard) is manual — no background scheduler, no Gmail push. It makes two bounded
query passes and classifies what it finds:

- A reply matching `stop|unsubscribe|no thanks|not interested|remove me|…` → suppressed as
  `reply_no`. Quoted text is stripped **before** matching, because our own footer says reply "no"
  and a friendly reply quoting the thread must not suppress someone who never asked.
- A **permanent** delivery failure (SMTP status `5.x.x`) → suppressed as `bounce`.
- A **soft** bounce (`4.x.x`), out-of-office or full mailbox → recorded, **never suppressed**.
  Suppressing on a transient failure permanently burns a legitimate prospect.

Suppression is the one thing the app never undoes automatically: re-importing a CSV or running a
sync will not resurrect an opted-out address.

---

## Operations

```bash
npm run dev          # API + UI together
npm run migrate      # apply pending schema migrations
npm run seed         # migrate + seed templates (idempotent)
npm run test         # pytest
npm run db:up        # start Postgres
npm run reconcile    # resolve stuck queued sends
```

Or per app: `nx dev api`, `nx test api`, `nx lint api`, `nx build web`, `nx typecheck web`.

To serve the built UI from the API on a single origin, run `nx build web` and set
`SERVE_FRONTEND=true`.

### Tests

```bash
cd apps/api && pytest
```

257 tests. Most are pure unit tests with no database, which is why the gate logic is the
best-covered part of the app:

| File                     | Covers                                                                 |
| ------------------------ | ---------------------------------------------------------------------- |
| `test_send_gates.py`     | Every blocker and warning; acknowledgement cannot clear a blocker       |
| `test_template_merge.py` | Substitution, leftover detection, idempotent opt-out / unsub append   |
| `test_csv_mapping.py`    | Header aliases, BOM/CRLF, dedupe, name splitting, encoding fallback    |
| `test_validation.py`     | Null MX, NXDOMAIN, A-record fallback, ZeroBounce status mapping        |
| `test_daily_cap_tz.py`   | The 14:00 UTC boundary, and concurrent reservations never exceed the cap |
| `test_send_path.py`      | Reserve/settle choreography, failure compensation, plain-text MIME     |
| `test_suppression.py`    | Auto-suppress, quoted-reply guard, soft bounces never suppress          |
| `test_unsub_token.py`    | Token entropy, GET is read-only, no enumeration oracle                 |
| `test_guards.py`         | Source scans: no SMTP, no ESP SDK, no bulk headers, no naive clock reads |

The database tests need `outreach_test`, which the Docker init script creates. If Postgres is not
reachable they skip rather than fail.

---

## Configuration

All backend config lives in `apps/api/.env` (see `.env.example`):

| Variable                       | Notes                                                              |
| ------------------------------ | ------------------------------------------------------------------ |
| `APP_BASE_URL`                 | Goes into every unsubscribe link; the OAuth redirect is derived from it |
| `FRONTEND_URL` / `CORS_ORIGIN` | Where the OAuth callback returns you                               |
| `DATABASE_URL`                 | Port 5433 for the Docker Postgres                                  |
| `SECRET_KEY`                   | Signs the session cookie, derives the token encryption key, HMACs OAuth state |
| `OUTREACH_APP_PASSWORD`        | The single app password                                            |
| `GOOGLE_CLIENT_ID` / `_SECRET` | From the Google Cloud OAuth client                                 |
| `ZEROBOUNCE_API_KEY`           | Optional. Blank → syntax + MX via dnspython                        |
| `DAILY_CAP`                    | Seeds the settings row only. Server ceiling is 50                  |
| `COOLDOWN_DAYS`                | Minimum days between emails to the same address (default 14)        |
| `TZ`                           | Informational only — date maths uses `ZoneInfo` explicitly          |

Rotating `SECRET_KEY` logs you out and makes the stored Gmail token undecryptable; just reconnect
Gmail. It does **not** break unsubscribe links already sitting in people's inboxes — tokens are
random and stored, not derived from the key.
