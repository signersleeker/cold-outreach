"""App-wide constants that are policy, not configuration."""

# Absolute server-side ceiling on the daily cap, independent of what the
# Settings page or DAILY_CAP says. The spec asks for a hard cap of 20 with a
# UI allowing up to 50; this is the number the server will never exceed.
HARD_MAX_DAILY_CAP = 50

# Above this the UI warns. One mailbox sending more than this per day is how
# a domain's reputation gets destroyed.
RECOMMENDED_DAILY_CAP = 20

SESSION_COOKIE_NAME = "kinnatic_outreach_session"

# CSV import limits. The import validates every row inline, so these bound how
# long one request can take.
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 500
IMPORT_VALIDATION_BUDGET_SECONDS = 25.0
IMPORT_VALIDATION_WORKERS = 8
