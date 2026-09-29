"""Gmail failure taxonomy.

The distinction matters for the daily cap. A send slot is reserved before the
Gmail call, so on failure we have to decide whether to give it back:

  GmailPermanentError  Gmail demonstrably never accepted the message (4xx).
                       Safe to release the slot.
  GmailAmbiguousError  Timeout, 429 or 5xx. The message may or may not have been
                       accepted. The slot stays consumed — under-sending is the
                       correct bias for a cap.
"""

from __future__ import annotations


class GmailError(RuntimeError):
    pass


class GmailNotConnectedError(GmailError):
    pass


class GmailPermanentError(GmailError):
    pass


class GmailAmbiguousError(GmailError):
    pass
