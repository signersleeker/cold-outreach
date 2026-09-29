"""Gmail API constants."""

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# gmail.send to deliver, gmail.readonly to read replies and bounces for the
# Sync inbox button. gmail.metadata cannot see message bodies, so it cannot
# support stop-word matching; readonly is the narrowest scope that works.
# gmail.settings.basic reads the sendAs signature so outbound mail can carry
# the same HTML footer the operator sees when composing in Gmail.
GMAIL_SETTINGS_SCOPE = "https://www.googleapis.com/auth/gmail.settings.basic"
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    GMAIL_SETTINGS_SCOPE,
)

OAUTH_STATE_TTL_MINUTES = 15

CONN_NOT_CONNECTED = "not_connected"
CONN_PENDING = "pending"
CONN_CONNECTED = "connected"
CONN_ERROR = "error"

# Headers that would make this look like bulk mail. Asserted absent in
# app/gmail/mime.py and covered by tests/sends/test_mime_plaintext_only.py.
FORBIDDEN_HEADERS = frozenset(
    {
        "list-unsubscribe",
        "list-unsubscribe-post",
        "list-id",
        "list-help",
        "list-owner",
        "list-post",
        "list-archive",
        "precedence",
        "auto-submitted",
        "x-campaign-id",
        "x-mailer",
        "x-mailgun-tag",
        "bulk",
    }
)
