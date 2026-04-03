"""
Build a full HTML page that renders a Markdown document (Agent OS / workbench viewer).
Uses PyPI `markdown` when installed; otherwise escapes and wraps in <pre> (install requirements-agent-os.txt).
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

_A_HREF_RE = re.compile(r'(<a\b[^>]*?\bhref\s*=\s*")([^"]*)(")', re.IGNORECASE)


def _md_to_fragment(source: str) -> str:
    try:
        import markdown as md_lib

        return md_lib.markdown(
            source,
            extensions=[
                "markdown.extensions.fenced_code",
                "markdown.extensions.tables",
                "markdown.extensions.nl2br",
            ],
        )
    except Exception:
        return (
            '<pre class="md-fallback"><code>'
            + html.escape(source)
            + "</code></pre>"
            + '<p class="md-fallback-note">Install <code>pip install -r requirements-agent-os.txt</code> for full Markdown rendering.</p>'
        )


def _split_href_fragment(href: str) -> tuple[str, str]:
    if "#" in href:
        i = href.index("#")
        return href[:i], href[i:]
    return href, ""


def _href_for_repo_rel(rel_posix: str) -> str | None:
    """Map a repo-relative path to a supervisor/workbench URL, or None if not allowed."""
    from scripts.os_dashboard_supervisor import _readonly_doc_path_allowed

    rel_posix = rel_posix.replace("\\", "/").lstrip("/")
    if not rel_posix or not _readonly_doc_path_allowed(rel_posix):
        return None
    suf = Path(rel_posix).suffix.lower()
    if suf in (".md", ".mdc"):
        return f"/view/markdown?path={quote(rel_posix, safe='')}"
    return "/" + rel_posix


def _resolve_href_for_viewer(href: str, source_repo_posix: str, repo_root: Path) -> str | None:
    """
    Turn an anchor target from Markdown into a same-origin URL that the supervisor can serve.
    Handles absolute disk paths, file:// URLs, root-absolute repo paths (/docs/...), and
    paths relative to the current document (fixes broken links under /view/markdown?path=...).
    """
    raw = html.unescape(href.strip())
    if not raw or raw.startswith("#"):
        return None
    low = raw.lower()
    if low.startswith("http://") or low.startswith("https://") or low.startswith("mailto:"):
        return None

    rr = repo_root.resolve()
    frag = ""

    if low.startswith("file://"):
        pu = urlparse(raw)
        base = unquote(pu.path)
        frag = f"#{pu.fragment}" if pu.fragment else ""
    else:
        base, frag = _split_href_fragment(raw)

    rel_out: str | None = None

    if low.startswith("file://"):
        try:
            rel = Path(base).resolve().relative_to(rr)
            rel_out = rel.as_posix()
        except ValueError:
            return None
    elif base.startswith("/") and not base.startswith("//"):
        try:
            resolved = Path(base).resolve()
            rel = resolved.relative_to(rr)
            rel_out = rel.as_posix()
        except ValueError:
            try:
                candidate = (rr / base.lstrip("/")).resolve()
                rel = candidate.relative_to(rr)
                rel_out = rel.as_posix()
            except ValueError:
                return None
    else:
        doc = Path(source_repo_posix.replace("\\", "/"))
        try:
            joined = (rr / doc.parent / base).resolve()
            rel = joined.relative_to(rr)
            rel_out = rel.as_posix()
        except ValueError:
            return None

    mapped = _href_for_repo_rel(rel_out) if rel_out else None
    if mapped is None:
        return None
    return mapped + frag


def _rewrite_markdown_anchor_hrefs(html_frag: str, source_repo_posix: str, repo_root: Path) -> str:
    rr = repo_root.resolve()

    def repl(m: re.Match[str]) -> str:
        prefix, href, suffix = m.group(1), m.group(2), m.group(3)
        new = _resolve_href_for_viewer(href, source_repo_posix, rr)
        if new is None:
            return m.group(0)
        return prefix + html.escape(new, quote=True) + suffix

    return _A_HREF_RE.sub(repl, html_frag)


def build_markdown_view_page(
    *,
    title: str,
    repo_path: str,
    source: str,
    repo_root: Path | None = None,
) -> str:
    body = _md_to_fragment(source)
    if repo_root is not None:
        body = _rewrite_markdown_anchor_hrefs(body, repo_path, repo_root)
    safe_title = html.escape(title)
    safe_path = html.escape(repo_path)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #050709;
      --accent: #00e8c8;
      --accent-soft: rgba(0,232,200,0.08);
      --text: #cce8e0;
      --muted: #5d7870;
      --line: rgba(0,232,200,0.10);
      --line-strong: rgba(0,232,200,0.18);
      --good-soft: rgba(74,222,128,0.12);
      --font-sans: "Plus Jakarta Sans", -apple-system, sans-serif;
      --font-display: "Bebas Neue", sans-serif;
      --font-mono: "DM Mono", ui-monospace, monospace;
      --font-size-xs: 11px;
      --font-size-sm: 13px;
      --font-size-base: 14px;
      --font-size-lg: 18px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --space-5: 24px;
      --radius-tight: 14px;
      --radius-card: 18px;
      --transition-base: 200ms ease;
    }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: var(--font-size-base);
      line-height: 1.55;
      padding: var(--space-5);
      width: 100%;
      max-width: min(1240px, calc(100vw - 32px));
      margin: 0 auto;
    }}
    :focus-visible {{ outline: 2px solid rgba(0,232,200,0.35); outline-offset: 2px; }}
    .viewer-header {{
      margin-bottom: var(--space-5);
      padding-bottom: var(--space-4);
      border-bottom: 1px solid var(--line);
    }}
    .viewer-eyebrow {{
      font-size: var(--font-size-xs);
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: var(--space-2);
    }}
    .viewer-path {{
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      color: var(--muted);
      word-break: break-all;
      margin-top: var(--space-2);
    }}
    .viewer-back {{
      display: inline-block;
      margin-top: var(--space-4);
      min-height: 44px;
      padding: 10px 12px;
      border-radius: var(--radius-tight);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      color: var(--accent);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      font-weight: 600;
      text-decoration: none;
      transition: background var(--transition-base), border-color var(--transition-base),
        transform var(--transition-base);
    }}
    .viewer-back:hover {{
      border-color: var(--line-strong);
      background: rgba(255,255,255,0.08);
      transform: translateY(-1px);
    }}
    .md-body :is(h1,h2,h3,h4) {{
      font-family: var(--font-display);
      font-weight: 400;
      letter-spacing: 0.05em;
      margin: var(--space-5) 0 var(--space-3);
      line-height: 1.15;
      color: var(--text);
    }}
    .md-body h1 {{ font-size: var(--font-size-lg); }}
    .md-body h2 {{ font-size: var(--font-size-base); border-bottom: 1px solid var(--line); padding-bottom: var(--space-2); }}
    .md-body h3 {{ font-size: var(--font-size-sm); color: var(--muted); }}
    .md-body p {{ margin: 0 0 var(--space-3); }}
    .md-body ul, .md-body ol {{ margin: 0 0 var(--space-3) var(--space-5); }}
    .md-body li {{ margin-bottom: var(--space-2); }}
    .md-body a {{ color: var(--accent); }}
    .md-body a:hover {{ text-decoration: underline; }}
    .md-body code {{
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      background: rgba(255,255,255,0.06);
      padding: 2px 6px;
      border-radius: var(--space-2);
      border: 1px solid var(--line);
    }}
    .md-body pre {{
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      background: rgba(0,0,0,0.35);
      border: 1px solid var(--line);
      border-radius: var(--radius-tight);
      padding: var(--space-3) var(--space-4);
      overflow-x: auto;
      margin: 0 0 var(--space-4);
    }}
    .md-body pre code {{
      background: none;
      border: none;
      padding: 0;
      font-size: inherit;
    }}
    .md-body blockquote {{
      border-left: 3px solid var(--accent);
      padding: var(--space-2) var(--space-4);
      margin: 0 0 var(--space-3);
      background: var(--accent-soft);
      color: var(--text);
    }}
    .md-body table {{
      border-collapse: collapse;
      width: 100%;
      margin: 0 0 var(--space-4);
      font-size: var(--font-size-sm);
    }}
    .md-body th, .md-body td {{
      border: 1px solid var(--line);
      padding: var(--space-2) var(--space-3);
      text-align: left;
    }}
    .md-body th {{
      background: var(--good-soft);
      font-weight: 600;
    }}
    .md-fallback {{
      white-space: pre-wrap;
      word-break: break-word;
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
    }}
    .md-fallback-note {{
      margin-top: var(--space-4);
      font-size: var(--font-size-sm);
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header class="viewer-header">
    <p class="viewer-eyebrow">Markdown preview</p>
    <h1 class="viewer-title" style="font-family:var(--font-display);font-size:var(--font-size-lg);font-weight:400;">{safe_title}</h1>
    <p class="viewer-path">{safe_path}</p>
    <a class="viewer-back" href="/docs/os-document-library.html">← Guides &amp; policies library</a>
  </header>
  <article class="md-body">
{body}
  </article>
</body>
</html>
"""
