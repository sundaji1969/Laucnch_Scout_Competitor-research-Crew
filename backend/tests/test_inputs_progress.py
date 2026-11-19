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
