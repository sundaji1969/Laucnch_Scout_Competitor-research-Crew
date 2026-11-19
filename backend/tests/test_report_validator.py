from pathlib import Path

import pytest

from app.services.report_validator import (
    REQUIRED_SECTIONS,
    ReportValidationError,
    assert_valid_report,
    validate_report,
)

GOOD = (Path(__file__).parent / "fixtures" / "good_report.md").read_text(encoding="utf-8")


def test_good_report_passes() -> None:
    r = validate_report(GOOD)
    assert r.ok, r.errors
    assert set(r.sections) == {k for k, _ in REQUIRED_SECTIONS}
    assert r.competitor_rows == 3
    assert r.citations == {1, 2, 3, 4}
    assert all(u.count("https://") == 1 for u in r.sources.values())


@pytest.mark.parametrize("_key,title", REQUIRED_SECTIONS)
def test_missing_section_fails(_key: str, title: str) -> None:
    broken = GOOD.replace(title, "Something Else")
    r = validate_report(broken)
    assert not r.ok
    assert any(title in e for e in r.errors)


def test_dangling_citation_fails() -> None:
    broken = GOOD.replace("No one offers", "No one offers [9]")
    r = validate_report(broken)
    assert any("[9]" in e for e in r.errors)


def test_source_without_url_fails() -> None:
    broken = GOOD.replace("https://www.instagram.com/ammastiffin", "instagram page")
    r = validate_report(broken)
    assert any("Source [4]" in e for e in r.errors)


def test_too_few_competitors_fails() -> None:
    lines = [ln for ln in GOOD.splitlines() if not ln.startswith("| Amma")]
    r = validate_report("\n".join(lines))
    assert any("Only 2 competitors" in e for e in r.errors)


def test_competitor_row_without_citation_fails() -> None:
    broken = GOOD.replace("No online ordering | [4] |", "No online ordering | - |")
    r = validate_report(broken)
    assert any("Amma's Tiffin" in e and "citation" in e for e in r.errors)


def test_assert_valid_raises_with_clear_message() -> None:
    with pytest.raises(ReportValidationError) as exc:
        assert_valid_report("# Empty report")
    assert "Missing section" in str(exc.value)


def test_bracket_sources_style_accepted() -> None:
    alt = GOOD.replace("1. Millet Kitchen menu", "[1] Millet Kitchen menu")
    assert validate_report(alt).ok
