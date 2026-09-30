# Threat model and compliance one-pager

Read this before the first real send. One page, no legal advice — just what the tool does, what it
deliberately does not do, and where the liability sits.

---

## 1. The thing to be clear about

**This tool sends unsolicited commercial electronic messages.**

Under the Australian **Spam Act 2003 (Cth)**, sending a commercial electronic message to an
Australian address requires the recipient's consent — express or inferred. The Act also requires
accurate sender identification and a functional, no-cost unsubscribe facility.

**This tool does not create, obtain, record or verify consent. Nothing in it makes a send lawful.**
The operator is the sender and carries the liability. A green "all gates pass" means the software's
own checks passed; it is not a legal opinion.

Penalties under the Act are civil and can be substantial, and they attach to the sender.

### What the tool does provide

- **Sender identification.** A real name, real title, the legal entity (`Kinnatic Pty Ltd`) and a
  real reply-to mailbox are appended to every message. A send is blocked outright if any of them is
  blank.
- **A functional unsubscribe facility.** Every email carries a unique `/u/{token}` link. It works
  without login, without JavaScript, and never expires. Using it suppresses the address immediately
  and permanently — well inside the Act's five-business-day ceiling for honouring an opt-out.
- **A second, human opt-out.** Every template ends with `If this isn't relevant, reply "no" and I
  won't email again.` The Sync inbox feature acts on such replies.
- **A permanent suppression list** that the send gate reads directly, on every send, as a hard
  blocker. Nothing in the app removes a suppression automatically — not a CSV re-import, not an
  inbox sync.

### What only you can provide

A defensible basis for contacting each specific person. That is why **`source` and `notes` are
prompted on import and shown on every contact**, and why sending without a `source` raises a
warning. They are your evidentiary record of where the address came from.

Inferred consent is narrow. It generally depends on a work address being conspicuously published
without a statement to the contrary, and the message being relevant to that person's role. A
published "no unsolicited commercial email" notice defeats it — check before importing, and record
what you checked.

---

## 2. Data

| Concern           | Position                                                                        |
| ----------------- | ------------------------------------------------------------------------------- |
| What is stored    | Names, work email addresses, employer, job title, and your own notes             |
| Legal character   | Personal information under the **Privacy Act 1988 (Cth)**                        |
| Where it lives    | A local Postgres database on your machine. Not hosted, not backed up by this app |
| Who else sees it  | Google (the mailbox you connect) and ZeroBounce (only if you configure a key)     |
| Retention         | Indefinite until you delete it. There is no automatic expiry                      |

APP 5 notification obligations may apply when you collect personal information. Suppressions are
kept indefinitely on purpose: deleting one would let a re-import resurrect someone who opted out.

---

## 3. Secrets

`SECRET_KEY` does three jobs — it signs the session cookie, derives the AES-GCM key that encrypts
the Gmail refresh token at rest, and HMACs the OAuth `state` parameter. **Leaking it means both
session forgery and token decryption.**

- It lives only in `apps/api/.env`, which is gitignored. Keep it that way.
- The Gmail refresh token is AES-GCM encrypted at rest and is never returned by any API response.
- Disconnecting Gmail revokes the grant at Google *before* deleting the local row, so a stale live
  grant is not left behind.
- Rotating `SECRET_KEY` logs you out and makes the stored Gmail token undecryptable — reconnect
  Gmail. It does **not** break unsubscribe links already delivered, because tokens are random and
  stored rather than derived from the key. That property is the whole reason for the design.

---

## 4. Attack surface

The app is single-user and password-gated. Only two routes are public:

- **`GET|POST /u/{token}`** — the unsubscribe page. Rate-limited per IP. `GET` has no side effects,
  so link scanners and corporate security gateways cannot unsubscribe people by prefetching.
  Unknown, malformed and already-used tokens render an identical neutral page with HTTP 200, so the
  endpoint is not an enumeration oracle. Tokens carry 256 bits of entropy and do not encode the
  address.
- **`GET /auth/google/callback`** — entered by Google's redirect, so it cannot require a session.
  Its authenticity comes from the HMAC-signed, 15-minute-expiring `state` parameter instead.

Login is rate-limited (8 attempts per 5 minutes) and the password is compared with
`hmac.compare_digest`. The session cookie is `HttpOnly`, `SameSite=Lax`, and signed.

**Known gap:** there is no CSRF token. Mitigations are `SameSite=Lax`, JSON-only mutations (which
force a CORS preflight cross-origin), and the app being single-user on localhost. If this ever gets
a public hostname, add a double-submit token. The unsubscribe `POST` is intentionally CSRF-free — a
forged unsubscribe is harmless.

Note that cookies ignore port, so anything else on `localhost` shares the cookie jar. The cookie is
named `kinnatic_outreach_session` to avoid colliding with other local projects.

---

## 5. Deliverability, and why the limits are the point

One mailbox, ≤20 sends/day, plain text, no tracking, no bulk headers,
and immediate suppression on any negative signal. **The constraints are the reputation strategy, not
a limitation to work around.**

- Raising the daily cap is the fastest way to get the mailbox flagged. The UI warns above 20 and the
  server refuses above 50 whatever is stored.
- The tool never opens an SMTP connection to a prospect's mail server. SMTP probing for validation
  is a reliable way to get a sending IP blocklisted; a source scan in the test suite enforces this.
- Hard bounces suppress. Soft bounces deliberately do not — suppressing on a transient failure burns
  a prospect who did nothing wrong.
- The cap fails closed. If Gmail's response is ambiguous, the slot stays consumed and you under-send
  rather than risk a double send.

---

## 6. Residual risks, stated plainly

1. **Consent is unverifiable by software.** The gates check deliverability and hygiene, not
   lawfulness. Only your `source` record answers "why was it defensible to email this person?"
2. **Stop-word matching is a regex.** It will miss politely phrased refusals ("I'll pass for now").
   Read your replies; do not rely on Sync inbox to catch everything.
3. **The disposable-domain list goes stale.** It is a floor, not a guarantee. ZeroBounce covers this
   properly when configured.
4. **An ambiguous Gmail failure is genuinely ambiguous.** Check the Sent folder, or run
   `nx reconcile api`, before retrying.
5. **External + Testing OAuth expires refresh tokens after 7 days**, and `gmail.readonly` is a
   Restricted scope requiring Google review to publish. Use Internal (Workspace) publishing.
6. **No audit log of operator actions.** Send events are recorded; edits and suppression removals are
   not.
