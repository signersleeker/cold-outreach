"""Migration version modules.

Add a new file here, then append it to MODULES in order.
"""

from __future__ import annotations

from app.migrations.versions import m0001_initial, m0002_include_unsub_link, m0003_companies

MODULES = (
    m0001_initial,
    m0002_include_unsub_link,
    m0003_companies,
)
