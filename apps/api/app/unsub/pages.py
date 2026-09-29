"""Server-rendered HTML for the public unsubscribe page. Pure — no I/O.

Deliberately plain: no React bundle, no CDN, no external font, no JavaScript. It
has to work in a locked-down corporate browser, on a phone, with images blocked.
"""

from __future__ import annotations

from html import escape

_STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px;
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
        Helvetica, Arial, sans-serif;
  background: #f5f5f4; color: #1c1917;
}
main {
  width: 100%; max-width: 30rem; background: #fff; border: 1px solid #e7e5e4;
  border-radius: 10px; padding: 28px 30px;
}
h1 { margin: 0 0 12px; font-size: 1.2rem; letter-spacing: -0.01em; }
p { margin: 0 0 14px; }
.email { font-weight: 600; word-break: break-all; }
.muted { color: #57534e; font-size: 0.875rem; margin-bottom: 0; }
button {
  font: inherit; font-weight: 600; cursor: pointer; margin-top: 8px;
  padding: 10px 18px; border-radius: 7px; border: 1px solid #1c1917;
  background: #1c1917; color: #fff;
}
button:hover { background: #292524; }
.ok { color: #15803d; font-weight: 600; }
@media (prefers-color-scheme: dark) {
  body { background: #1c1917; color: #f5f5f4; }
  main { background: #292524; border-color: #44403c; }
  .muted { color: #a8a29e; }
  button { background: #f5f5f4; color: #1c1917; border-color: #f5f5f4; }
  button:hover { background: #e7e5e4; }
  .ok { color: #4ade80; }
}
"""


def _page(title: str, body_html: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        # Keep this page out of search engines and stop link scanners following it.
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><main>{body_html}</main></body></html>"
    )


def confirm_page(email: str, company_legal: str, token: str) -> str:
    """The GET page: a confirmation, not an action.

    A side-effecting GET would be unsafe here — mail clients and corporate
    security gateways prefetch links in received mail, which would silently
    unsubscribe people who never clicked. The POST below is the action.
    """
    return _page(
        "Unsubscribe",
        f"<h1>Stop emails to this address?</h1>"
        f'<p>We will stop sending to <span class="email">{escape(email)}</span> '
        f"and will not contact it again.</p>"
        f'<form method="post" action="/u/{escape(token)}">'
        f"<button type=\"submit\">Yes, unsubscribe me</button></form>"
        f'<p class="muted" style="margin-top:18px">Sent by {escape(company_legal)}. '
        f"You can also just reply &ldquo;no&rdquo; to the email.</p>",
    )


def done_page(email: str, company_legal: str) -> str:
    return _page(
        "Unsubscribed",
        f'<h1><span class="ok">Done.</span> You are unsubscribed.</h1>'
        f'<p>No further email will be sent to <span class="email">{escape(email)}</span>.</p>'
        f'<p class="muted">{escape(company_legal)}</p>',
    )


def invalid_page() -> str:
    """Shown for unknown, malformed, or already-used tokens.

    One neutral page for every failure mode, returned with HTTP 200, so the
    endpoint is not an oracle for which tokens exist.
    """
    return _page(
        "Link no longer valid",
        "<h1>This link is no longer valid.</h1>"
        "<p>It may have already been used, or it may have expired.</p>"
        '<p class="muted">If you are still receiving email you did not ask for, '
        "reply to it with &ldquo;no&rdquo; and it will stop.</p>",
    )
