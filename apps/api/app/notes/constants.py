"""Which records a note can belong to."""

NOTABLE_CONTACT = "contact"
NOTABLE_COMPANY = "company"

NOTABLE_TYPES = frozenset({NOTABLE_CONTACT, NOTABLE_COMPANY})

MAX_NOTE_BODY = 10_000
