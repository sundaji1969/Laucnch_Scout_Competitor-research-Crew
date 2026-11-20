from app.crew.inputs import RunInputs
from app.crew.progress import describe_tool_call, summarise_tool_result


def test_inputs_are_sanitised() -> None:
    r = RunInputs(
        business_idea="  Millet <script>x</script> boxes {city} ",
        city="Coimbatore\x00",
        target_customer="Office workers",
        known_competitors="A, b , a, ,C",  # type: ignore[arg-type]
    )
    assert "<script>" not in r.business_idea
    assert "{" not in r.business_idea
    assert r.city == "Coimbatore"
    assert r.known_competitors == ["A", "b", "C"]


def test_tool_descriptions() -> None:
    assert describe_tool_call("Search the internet with Serper", {"search_query": "millet cbe"}) == (
        "Searching: millet cbe"
    )
    assert describe_tool_call("Read website content", '{"website_url": "https://x.com/a"}') == (
        "Reading: https://x.com/a"
    )
    s = summarise_tool_result(
        "Search the internet with Serper",
        {"organic": [{"link": "https://www.swiggy.com/a"}, {"link": "https://zomato.com/b"}]},
    )
    assert s.startswith("2 results")
    assert "swiggy.com" in s
    assert summarise_tool_result("Read website content", "SCRAPE FAILED for x. blah").startswith(
        "SCRAPE FAILED"
    )


def test_scrape_summary_names_site() -> None:
    msg = summarise_tool_result(
        "Read website content", "x" * 12015, {"website_url": "https://www.sniffy.in/p"}
    )
    assert msg == "Read sniffy.in · 12k characters"


def test_delegation_lines_in_the_feed() -> None:
    from app.crew.progress import describe_tool_call, summarise_tool_result

    args = {
        "coworker": "Local Market Researcher for Coimbatore",
        "task": "Find 3 to 5 real competitors for millet lunch boxes in Coimbatore. Include prices.",
        "context": "...",
    }
    assert describe_tool_call("Delegate work to coworker", args) == (
        "Delegating to Market Researcher: Find 3 to 5 real competitors for millet lunch boxes in Coimbatore."
    )
    assert (
        describe_tool_call(
            "Ask question to coworker", {"coworker": "Customer Review Analyst", "question": "Which source?"}
        )
        == "Asking Review Analyst: Which source?"
    )
    assert summarise_tool_result("Delegate work to coworker", '{"competitors": []}', args) == (
        "Market Researcher reported back"
    )


def test_prefer_complete_report(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from pathlib import Path

    from app.crew.runner import _prefer_complete_report

    good = (Path(__file__).parent / "fixtures" / "good_report.md").read_text(encoding="utf-8")
    saved = tmp_path / "report.md"
    assert _prefer_complete_report("The report has been saved to report.md.", saved) == (
        "The report has been saved to report.md."
    )  # nothing saved: keep the answer (validation will fail it clearly)
    saved.write_text(good, encoding="utf-8")
    assert _prefer_complete_report("The report has been saved to report.md.", saved).strip() == good.strip()
    assert _prefer_complete_report(good, saved) == good  # complete answer wins ties
