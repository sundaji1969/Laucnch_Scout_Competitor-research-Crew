import json
from types import SimpleNamespace

from app.crew.guardrails import check_competitor_list, competitor_list_guardrail
from app.crew.schemas import NOT_LISTED, CompetitorList


def _comp(name: str, price: str = "₹150 per meal", urls: list[str] | None = None) -> dict:
    return {
        "name": name,
        "price_per_unit": price,
        "source_urls": urls if urls is not None else [f"https://example.com/{name}"],
    }


def _payload(*comps: dict) -> dict:
    return {"business_idea": "millet meals", "city": "Coimbatore", "competitors": list(comps)}


def test_accepts_three_valid_competitors() -> None:
    data = _payload(_comp("a"), _comp("b"), _comp("c", price=NOT_LISTED))
    out = SimpleNamespace(pydantic=CompetitorList.model_validate(data))
    ok, result = competitor_list_guardrail(out)
    assert ok
    assert result is out


def test_rejects_fewer_than_three() -> None:
    data = _payload(_comp("a"), _comp("b"))
    ok, msg = competitor_list_guardrail(SimpleNamespace(pydantic=None, json_dict=data, raw=""))
    assert not ok
    assert "Only 2 competitors" in msg


def test_rejects_missing_source() -> None:
    data = _payload(_comp("a"), _comp("b"), _comp("c", urls=[]))
    problems = check_competitor_list(SimpleNamespace(pydantic=None, json_dict=None, raw=json.dumps(data)))
    assert problems and "not a valid CompetitorList" in problems[0]


def test_rejects_empty_price() -> None:
    data = _payload(_comp("a"), _comp("b"), _comp("c", price="   "))
    ok, msg = competitor_list_guardrail(SimpleNamespace(pydantic=None, json_dict=None, raw=json.dumps(data)))
    assert not ok
    assert "'c' has no price" in msg


def test_rejects_duplicates() -> None:
    data = _payload(_comp("a"), _comp("A"), _comp("b"))
    assert any("Duplicate" in p for p in check_competitor_list(data))


def test_parses_fenced_json() -> None:
    data = _payload(_comp("a"), _comp("b"), _comp("c"))
    raw = "```json\n" + json.dumps(data) + "\n```"
    assert check_competitor_list(SimpleNamespace(pydantic=None, json_dict=None, raw=raw)) == []
