from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.pdf import render_pdf, report_html

GOOD = (Path(__file__).parent / "fixtures" / "good_report.md").read_text(encoding="utf-8")


def _html() -> str:
    return report_html(
        GOOD,
        idea="Millet boxes <b>",
        city="Coimbatore",
        target_customer="Office workers",
        created=datetime(2026, 11, 19, tzinfo=UTC),
    )


def test_html_has_cover_tables_and_clickable_citations() -> None:
    h = _html()
    assert 'class="cover"' in h
    assert "Millet boxes &lt;b&gt;" in h  # escaped user input
    assert "<table>" in h
    assert '<a class="cite" href="#source-1">[1]</a>' in h
    assert '<li id="source-4">' in h
    assert '<a href="https://www.instagram.com/ammastiffin">' in h


def _weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


@pytest.mark.skipif(not _weasyprint_available(), reason="WeasyPrint system libraries not installed")
def test_render_pdf() -> None:
    pdf = render_pdf(_html())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
