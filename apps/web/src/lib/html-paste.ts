/**
 * Pasting Gmail into a textarea keeps only text/plain, which drops the address
 * behind a linked word. This turns those anchors into [label](https://...)
 * so the template can store the link. The same pattern is read by
 * PLAIN_LINK / _PLAIN_LINK_RE in apps/api/app/gmail/mime.py.
 */

const PLAIN_LINK = /\[([^\[\]\n]+)\]\((https?:\/\/[^\s<>"')\]]+)\)/g;

const BLOCK_GAP: Record<string, '\n' | '\n\n'> = {
  ADDRESS: '\n',
  ARTICLE: '\n',
  ASIDE: '\n',
  BLOCKQUOTE: '\n\n',
  DD: '\n',
  DIV: '\n',
  DL: '\n',
  DT: '\n',
  FIGCAPTION: '\n',
  FIGURE: '\n',
  FOOTER: '\n',
  H1: '\n\n',
  H2: '\n\n',
  H3: '\n\n',
  H4: '\n\n',
  H5: '\n\n',
  H6: '\n\n',
  HEADER: '\n',
  LI: '\n',
  OL: '\n',
  P: '\n\n',
  PRE: '\n',
  SECTION: '\n',
  TABLE: '\n',
  TR: '\n',
  UL: '\n',
};

const SKIP = new Set(['HEAD', 'LINK', 'META', 'SCRIPT', 'STYLE', 'TITLE']);

type State = { kept: boolean };

export function plainLinks(text: string): { label: string; href: string }[] {
  return [...text.matchAll(PLAIN_LINK)].map((match) => ({
    label: match[1] ?? '',
    href: match[2] ?? '',
  }));
}

/** Plain text with [label](url) for linked words, or null when nothing would be lost. */
export function htmlClipboardToPlain(html: string): string | null {
  if (!html || !/<a[\s>]/i.test(html)) return null;
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const state: State = { kept: false };
  const text = tidy(renderChildren(doc.body, state, false));
  if (!state.kept || !text) return null;
  return text;
}

function renderChildren(el: ParentNode, state: State, inAnchor: boolean): string {
  return Array.from(el.childNodes)
    .map((node) => renderNode(node, state, inAnchor))
    .join('');
}

function renderNode(node: Node, state: State, inAnchor: boolean): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return (node.textContent ?? '').replace(/\u00a0/g, ' ');
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return '';
  const el = node as HTMLElement;
  const tag = el.tagName;
  if (SKIP.has(tag)) return '';
  if (tag === 'BR' || tag === 'HR') return '\n';
  if (tag === 'IMG') return el.getAttribute('alt') ?? '';
  if (tag === 'A') {
    if (inAnchor) return renderChildren(el, state, true);
    return renderAnchor(el, state);
  }
  const inner = renderChildren(el, state, inAnchor);
  const gap = BLOCK_GAP[tag];
  if (!gap) return inner;
  return closeBlock(inner, gap);
}

function renderAnchor(el: HTMLElement, state: State): string {
  const href = unwrapHref(stripInvisibles(el.getAttribute('href') ?? '').replace(/\s+/g, ''));
  const label = tidyInline(renderChildren(el, state, true));
  if (!isSafeHttpUrl(href)) return label;
  if (!label || label === href || label === href.replace(/\/$/, '')) {
    // An image or empty anchor has no words, so the address itself has to survive.
    if (!label) state.kept = true;
    return href;
  }
  state.kept = true;
  return `[${sanitizeLabel(label)}](${sanitizeHref(href)})`;
}

function closeBlock(inner: string, gap: '\n' | '\n\n'): string {
  const core = inner.replace(/\n+$/g, '').replace(/[ \t]+$/g, '');
  if (!core.trim()) return '\n';
  return core + gap;
}

function tidy(text: string): string {
  return text
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/^\n+|\n+$/g, '');
}

function tidyInline(text: string): string {
  return stripInvisibles(text)
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function sanitizeLabel(label: string): string {
  return label.replace(/[\[\]]/g, '');
}

function sanitizeHref(href: string): string {
  return href.replaceAll('(', '%28').replaceAll(')', '%29');
}

function stripInvisibles(value: string): string {
  return value.replace(/[\u200b\u200c\u200d\ufeff]/g, '');
}

function isSafeHttpUrl(href: string): boolean {
  if (!href || href.length > 2048) return false;
  try {
    const url = new URL(href);
    if (url.username || url.password) return false;
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

function unwrapHref(href: string): string {
  let current = href;
  for (let i = 0; i < 2; i += 1) {
    let url: URL;
    try {
      url = new URL(current);
    } catch {
      return current;
    }
    if (!isGoogleRedirect(url)) return current;
    const next = url.searchParams.get('q') || url.searchParams.get('url') || '';
    if (!/^https?:\/\//i.test(next)) return current;
    current = next;
  }
  return current;
}

function isGoogleRedirect(url: URL): boolean {
  return (
    url.pathname === '/url' &&
    /(^|\.)google\.([a-z]{2,3})(\.[a-z]{2})?$/i.test(url.hostname)
  );
}
