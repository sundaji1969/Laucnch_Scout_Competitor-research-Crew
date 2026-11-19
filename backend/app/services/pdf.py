"""Markdown report -> branded HTML -> PDF (WeasyPrint).

The HTML step is pure Python (markdown-it) and unit-testable everywhere; WeasyPrint
needs Pango/Cairo system libraries, which the Docker image provides.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

from markdown_it import MarkdownIt

_CITE_RE = re.compile(r"\[(\d{1,3})\](?![(:])")

CSS = """
@page {
  size: A4; margin: 22mm 18mm 20mm;
  @bottom-left { content: "LaunchScout · Competitor report"; font: 8pt 'Inter', sans-serif; color: #8a8f98; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt 'Inter', sans-serif; color: #8a8f98; }
}
@page :first { margin: 0; @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
body { font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; line-height: 1.55;
       color: #1d2130; }
.cover { page-break-after: always; height: 297mm; padding: 34mm 24mm; color: #f5f3ee;
         background: #12141c; display: flex; flex-direction: column; justify-content: space-between; }
.cover .brand { font-size: 10pt; letter-spacing: .18em; text-transform: uppercase; color: #e8b04b; }
.cover h1 { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: 30pt; line-height: 1.15;
            margin: 0 0 8mm; color: #f5f3ee; }
.cover .meta { font-size: 10pt; color: #b9bcc6; }
.cover .meta b { color: #f5f3ee; font-weight: 600; }
.cover .rule { width: 28mm; height: 2px; background: #e8b04b; margin-bottom: 8mm; }
main h1 { display: none; }
h2 { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: 16pt; color: #12141c;
     margin: 9mm 0 3mm; padding-bottom: 2mm; border-bottom: 1px solid #e4e1d8; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 5mm 0 1.5mm; color: #12141c; }
p, li { orphans: 3; widows: 3; }
table { width: 100%; border-collapse: collapse; font-size: 8.5pt; margin: 3mm 0 5mm; page-break-inside: auto; }
th { text-align: left; background: #f4f1ea; color: #12141c; font-weight: 600; padding: 2mm 2.2mm;
     border-bottom: 1.5px solid #12141c; }
td { padding: 2mm 2.2mm; border-bottom: 1px solid #ebe8e0; vertical-align: top; }
tr { page-break-inside: avoid; }
a { color: #a8711a; text-decoration: none; }
a.cite { font-size: 7.5pt; font-weight: 600; vertical-align: super; line-height: 0; padding: 0 .3mm; }
ol.sources li, #sources + ol li { word-break: break-all; margin-bottom: 1.2mm; font-size: 8.5pt; }
strong { color: #12141c; }
hr { border: 0; border-top: 1px solid #e4e1d8; }
"""


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")


def _link_citations(body_html: str) -> str:
    return _CITE_RE.sub(
        lambda m: f'<a class="cite" href="#source-{m.group(1)}">[{m.group(1)}]</a>', body_html
    )


def _anchor_sources(body_html: str) -> str:
    """Give each <li> in the list that follows the Sources heading an id, and linkify URLs."""
    idx = body_html.lower().rfind("sources</h2>")
    if idx < 0:
        return body_html
    head, tail = body_html[:idx], body_html[idx:]
    m = re.search(r"<ol(?: start=\"(\d+)\")?>", tail)
    if not m:
        return body_html
    start = int(m.group(1) or 1)
    counter = iter(range(start, start + 1000))

    def li(match: re.Match[str]) -> str:
        return f'<li id="source-{next(counter)}">'

    end = tail.find("</ol>", m.end())
    ol_body = re.sub(r"<li>", li, tail[m.end() : end])
    ol_body = re.sub(
        r"(?<![\"'>])(https?://[^\s<]+)", lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', ol_body
    )
    return head + tail[: m.start()] + '<ol class="sources">' + ol_body + tail[end:]


def report_html(markdown: str, *, idea: str, city: str, target_customer: str, created: datetime) -> str:
    body = _md().render(markdown)
    sources_at = body.lower().rfind("sources</h2>")
    if sources_at > 0:
        body = _link_citations(body[:sources_at]) + body[sources_at:]
    body = _anchor_sources(body)
    e = html.escape
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{e(idea)} in {e(city)} · LaunchScout</title>
<style>{CSS}</style></head>
<body>
<section class="cover">
  <div class="brand">LaunchScout</div>
  <div>
    <div class="rule"></div>
    <h1>{e(idea)}<br>in {e(city)}</h1>
    <div class="meta">Competitor research report<br>
      Target customer: <b>{e(target_customer)}</b><br>
      Generated {created.strftime("%d %B %Y")}</div>
  </div>
  <div class="meta">Every price and claim is cited to a numbered source. Verify before you invest.</div>
</section>
<main>{body}</main>
</body></html>"""


def render_pdf(html_doc: str) -> bytes:
    from weasyprint import HTML  # imported lazily: needs system libraries

    pdf = HTML(string=html_doc).write_pdf()
    assert pdf is not None
    return bytes(pdf)
