"""Suppression reasons.

A suppression is permanent and is the one thing that must never be lost: it is
how an opt-out is honoured. Nothing in the app deletes suppressions implicitly.
"""

REASON_UNSUB = "unsub"
REASON_BOUNCE = "bounce"
REASON_COMPLAINT = "complaint"
REASON_MANUAL = "manual"
REASON_REPLY_NO = "reply_no"

REASONS = frozenset(
    {REASON_UNSUB, REASON_BOUNCE, REASON_COMPLAINT, REASON_MANUAL, REASON_REPLY_NO}
)

REASON_LABELS = {
    REASON_UNSUB: "Used the unsubscribe link",
    REASON_BOUNCE: "Permanent delivery failure",
    REASON_COMPLAINT: "Spam complaint",
    REASON_MANUAL: "Added manually",
    REASON_REPLY_NO: "Replied asking to stop",
}
