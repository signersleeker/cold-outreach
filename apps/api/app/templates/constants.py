"""Merge variables and the seeded default templates."""

# first_name is required: a cold email opening "Hi ," is indefensible.
REQUIRED_VARS = frozenset({"first_name"})

# Optional on the contact, but blocking if a template references one and the
# contact lacks it — an unrendered {{company}} must never go out.
OPTIONAL_VARS = frozenset({"last_name", "company", "title", "hook"})

# Supplied by the settings singleton.
IDENTITY_VARS = frozenset({"sender_name", "sender_title", "company_legal"})

KNOWN_VARS = REQUIRED_VARS | OPTIONAL_VARS | IDENTITY_VARS

OPT_OUT_SENTENCE = 'If this isn\'t relevant, reply "no" and I won\'t email again.'

DEFAULT_SENDER_NAME = "Joey"
DEFAULT_SENDER_TITLE = "CEO"
DEFAULT_COMPANY_LEGAL = "Kinnatic Pty Ltd"

FIRST_TOUCH_NAME = "CISO shadow AI"
# No merge tags in the subject on purpose: {{company}} here would hard-block
# every contact with a blank company for no benefit.
FIRST_TOUCH_SUBJECT = "shadow AI + pre-execution control"
FIRST_TOUCH_BODY = """Hi {{first_name}},

I work with {{title}} types at regulated orgs on shadow AI and pre-execution control (APRA / on-prem / audit trail), not another Copilot wrapper.

If {{company}} is already tight on this, ignore. If useful I can send a one-pager.

Joey
Kinnatic Pty Ltd
If this isn't relevant, reply "no" and I won't email again."""

FOLLOW_UP_NAME = "Follow up"
FOLLOW_UP_SUBJECT = "re: shadow AI + pre-execution control"
FOLLOW_UP_BODY = """Hi {{first_name}},

Following up once on the note below, then I'll leave it.

Joey
Kinnatic Pty Ltd
If this isn't relevant, reply "no" and I won't email again."""
