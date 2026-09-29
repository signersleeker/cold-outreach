"""Resolve sends whose outcome was never observed.

    python -m app.cli.reconcile_sends

A send_event stuck in `queued` means the process was interrupted between the
Gmail call and the commit that records its result. Because we generate and store
the RFC 822 Message-ID before sending, the truth is recoverable: search Gmail for
`rfc822msgid:<id>`.

  found     -> the message did go out. Promote to `sent`, keep the slot consumed.
  not found -> after the grace period it never went out. Mark `failed` and give
               the daily slot back.
"""

from __future__ import annotations

import datetime as dt
import sys

from dotenv import load_dotenv

from app.config import get_settings
from app.database import SessionLocal, import_all_models, reset_engine
from app.gmail.exceptions import GmailError
from app.gmail.oauth_service import GmailOAuthService, OAuthConfig
from app.lib.clock import BRISBANE, SystemClock, ensure_aware
from app.sends.constants import SEND_STATUS_FAILED, SEND_STATUS_SENT
from app.sends.services import counters
from app.sends.services.send import SendService

# Only give a slot back once we are confident it truly never sent.
GRACE_MINUTES = 60


def main() -> int:
    load_dotenv(".env", override=True)
    get_settings.cache_clear()
    reset_engine()
    import_all_models()

    settings = get_settings()
    clock = SystemClock()
    oauth = GmailOAuthService(
        OAuthConfig(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_url=settings.google_redirect_url(),
            state_secret=settings.secret_key,
            encryption_key=settings.secret_key,
            frontend_url=settings.resolved_frontend_url(),
        ),
        clock,
    )
    sends = SendService(settings=settings, oauth=oauth, clock=clock)

    db = SessionLocal()
    try:
        if not oauth.is_connected(db):
            print("no Gmail mailbox is connected; nothing to reconcile against.")
            return 1

        stuck = sends.stuck_queued(db)
        if not stuck:
            print("nothing to reconcile: no queued sends.")
            return 0

        client = oauth.client(db)
        promoted = failed = undecided = 0
        now = clock.now()

        for event in stuck:
            try:
                gmail_id = client.find_by_rfc822_id(event.rfc822_message_id)
            except GmailError as exc:
                print(f"  {event.id}: lookup failed ({exc}); leaving as queued")
                undecided += 1
                continue

            if gmail_id:
                event.status = SEND_STATUS_SENT
                event.gmail_message_id = gmail_id
                event.sent_at = event.sent_at or event.created_at
                event.settled_at = now
                db.add(event)
                promoted += 1
                print(f"  {event.id}: found in Gmail -> sent")
                continue

            created_at = ensure_aware(event.created_at)
            if now - created_at < dt.timedelta(minutes=GRACE_MINUTES):
                undecided += 1
                print(f"  {event.id}: not found yet, still inside the grace period")
                continue

            event.status = SEND_STATUS_FAILED
            event.error = "reconciled: never appeared in Gmail"
            event.settled_at = now
            db.add(event)
            # Release the slot for the day the send was reserved on, not today —
            # a stuck send from last week consumed last week's quota.
            reserved_day = created_at.astimezone(BRISBANE).date()
            counters.release_daily_slot(db, reserved_day)
            failed += 1
            print(f"  {event.id}: never sent -> failed, slot released for {reserved_day}")

        db.commit()
        print(f"\npromoted {promoted}, failed {failed}, still undecided {undecided}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
