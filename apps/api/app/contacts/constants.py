"""Contact constants: validation vocabulary, CSV aliases, consumer domains."""

VALIDATION_PENDING = "pending"
VALIDATION_VALID = "valid"
VALIDATION_INVALID = "invalid"
VALIDATION_RISKY = "risky"
VALIDATION_UNKNOWN = "unknown"

VALIDATION_STATUSES = frozenset(
    {
        VALIDATION_PENDING,
        VALIDATION_VALID,
        VALIDATION_INVALID,
        VALIDATION_RISKY,
        VALIDATION_UNKNOWN,
    }
)

# CSV header aliases. Keys are headers after normalisation (lowercased, BOM and
# punctuation stripped, whitespace collapsed to "_"); values are model fields.
HEADER_ALIASES: dict[str, str] = {
    # email
    "email": "email",
    "email_address": "email",
    "e_mail": "email",
    "work_email": "email",
    "business_email": "email",
    "primary_email": "email",
    # first name
    "first_name": "first_name",
    "first": "first_name",
    "firstname": "first_name",
    "given_name": "first_name",
    "fname": "first_name",
    # last name
    "last_name": "last_name",
    "last": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "family_name": "last_name",
    "lname": "last_name",
    # full name — split on import when first/last are absent
    "name": "full_name",
    "full_name": "full_name",
    "contact_name": "full_name",
    # company
    "company": "company",
    "company_name": "company",
    "organisation": "company",
    "organization": "company",
    "account": "company",
    "employer": "company",
    # title
    "title": "title",
    "job_title": "title",
    "jobtitle": "title",
    "position": "title",
    "role": "title",
    # the rest
    "hook": "hook",
    "angle": "hook",
    "notes": "notes",
    "note": "notes",
    "comments": "notes",
    "source": "source",
    "source_url": "source",
    "lead_source": "source",
    "url": "source",
}

# Free mailbox providers. Not invalid — but a B2B row on one of these usually
# means the address was guessed rather than found, so it warns.
CONSUMER_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.com.au",
        "ymail.com",
        "outlook.com",
        "outlook.com.au",
        "hotmail.com",
        "hotmail.com.au",
        "live.com",
        "live.com.au",
        "msn.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "gmx.com",
        "mail.com",
        "bigpond.com",
        "optusnet.com.au",
        "iinet.net.au",
        "tpg.com.au",
    }
)

CONTACT_FILTERS = frozenset({"all", "ready", "risky", "invalid", "pending", "sent", "suppressed"})
