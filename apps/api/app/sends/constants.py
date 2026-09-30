"""Send statuses and gate codes.

Gate codes are a stable API contract: the frontend maps them to labels and
tones in apps/web/src/lib/gates.ts. Renaming one is a breaking change.
"""

SEND_STATUS_QUEUED = "queued"
SEND_STATUS_SENT = "sent"
SEND_STATUS_FAILED = "failed"
SEND_STATUS_BOUNCED = "bounced"
SEND_STATUS_REPLIED_STOP = "replied_stop"

SEND_STATUSES = frozenset(
    {
        SEND_STATUS_QUEUED,
        SEND_STATUS_SENT,
        SEND_STATUS_FAILED,
        SEND_STATUS_BOUNCED,
        SEND_STATUS_REPLIED_STOP,
    }
)

# --- blockers: the send is refused -------------------------------------------
GATE_GMAIL_NOT_CONNECTED = "gmail_not_connected"
GATE_SETTINGS_INCOMPLETE = "settings_incomplete"
GATE_TEMPLATE_MISSING = "template_missing"
GATE_EMAIL_INVALID = "email_invalid"
GATE_CONTACT_SUPPRESSED = "contact_suppressed"
GATE_DAILY_CAP_REACHED = "daily_cap_reached"
GATE_UNRENDERED_MERGE_TAGS = "unrendered_merge_tags"
GATE_SUBJECT_EMPTY = "subject_empty"
GATE_BODY_EMPTY = "body_empty"
GATE_WARNING_NOT_ACKNOWLEDGED = "warning_not_acknowledged"

# --- warnings: the send proceeds, but the operator should look ---------------
GATE_VALIDATION_RISKY = "validation_risky"
GATE_VALIDATION_PENDING = "validation_pending"
GATE_VALIDATION_UNKNOWN = "validation_unknown"
GATE_CONSUMER_DOMAIN = "consumer_domain"
GATE_MISSING_COMPANY = "missing_company"
GATE_MULTIPLE_LINKS = "multiple_links"
