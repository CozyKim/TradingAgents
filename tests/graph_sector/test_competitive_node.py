import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.competitive_landscape import (
    make_competitive_node,
)
from tradingagents.graph_sector.state import SectorState

_VALID = {
    "companies": [
        {
            "name": "ASML", "ticker": "ASML", "stage": "Upstream — 노광장비",
            "share_value": 65.0, "share_basis": "reported",
            "confidence": "high", "sources": ["https://example.com/1"]
        },
        {
            "name": "Applied Materials", "ticker": "AMAT",
            "stage": "Upstream — 식각/증착",
            "share_value": 18.0, "share_basis": "estimated",
            "confidence": "medium", "sources": []
        },
    ]
}


def test_companies_parsed():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))
    node = make_competitive_node(llm, budget=None)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    result = node(state)
    assert len(result["companies"]) == 2
    assert result["companies"][0]["share_basis"] == "reported"


def test_unknown_basis_fallback():
    bad = {"companies": [{"name": "X", "stage": "?", "share_value": 10.0,
                          "share_basis": "totally_wrong",
                          "confidence": "high", "sources": []}]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(bad))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"][0]["share_basis"] == "unknown"


def test_share_value_non_numeric_falls_back_to_zero():
    """LLM may return 'N/A', null, '?'... the node must not crash."""
    for bad_value in [None, "N/A", "?", "n/a", "정보 없음"]:
        payload = {"companies": [{
            "name": "X", "stage": "?", "share_value": bad_value,
            "share_basis": "estimated", "confidence": "medium", "sources": [],
        }]}
        llm = MagicMock()
        llm.bind_tools.return_value = llm
        llm.invoke.return_value = AIMessage(content=json.dumps(payload))
        node = make_competitive_node(llm, budget=None)
        result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
        assert result["companies"][0]["share_value"] == 0.0
        # Falling back to 0.0 means the original basis claim is no longer trustworthy
        assert result["companies"][0]["share_basis"] == "unknown"


def test_share_value_out_of_range_clamped():
    """Numeric but out-of-range (e.g. 120, -5) must clamp to 0..100 AND mark unknown.

    CompanyShare Pydantic schema enforces ge=0, le=100 — without this guard
    a 120 would crash response serialization downstream.
    """
    for bad_value, expected in [(120.0, 100.0), (-5.0, 0.0), (200, 100.0)]:
        payload = {"companies": [{
            "name": "X", "stage": "?", "share_value": bad_value,
            "share_basis": "reported", "confidence": "high", "sources": [],
        }]}
        llm = MagicMock()
        llm.bind_tools.return_value = llm
        llm.invoke.return_value = AIMessage(content=json.dumps(payload))
        node = make_competitive_node(llm, budget=None)
        result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
        assert result["companies"][0]["share_value"] == expected
        assert result["companies"][0]["share_basis"] == "unknown"


def test_sources_string_wrapped_to_singleton_list():
    """LLM may return sources as a bare URL string — wrap into [url], do not split chars."""
    payload = {"companies": [{
        "name": "X", "stage": "?", "share_value": 50,
        "share_basis": "reported", "confidence": "high",
        "sources": "https://example.com",  # bare string, not list
    }]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(payload))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"][0]["sources"] == ["https://example.com"]


def test_sources_null_becomes_empty():
    payload = {"companies": [{
        "name": "X", "stage": "?", "share_value": 50,
        "share_basis": "reported", "confidence": "high",
        "sources": None,
    }]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(payload))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"][0]["sources"] == []


def test_sources_non_url_strings_dropped():
    """LLM may put 'IDC 보고서', 'N/A', etc. in sources — must be filtered.

    CompanyShare.sources is list[HttpUrl] so anything non-URL would 500
    the response serializer.
    """
    payload = {"companies": [{
        "name": "X", "stage": "?", "share_value": 50,
        "share_basis": "reported", "confidence": "high",
        "sources": [
            "IDC 보고서",          # not a URL
            "N/A",                # not a URL
            "https://example.com/good",
            "ftp://nope.com",     # wrong scheme
            "",                   # empty
            "https://example.com/another",
        ],
    }]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(payload))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"][0]["sources"] == [
        "https://example.com/good",
        "https://example.com/another",
    ]


def test_companies_with_non_dict_elements_falls_back():
    """JSON parses but {"companies": ["ASML"]} — element is a str, not dict.

    Without the element-type guard _normalize_company would crash on c.get().
    The retry path must catch this.
    """
    bad = {"companies": ["ASML", {"name": "TSMC", "stage": "Mid",
                                  "share_value": 50, "share_basis": "estimated",
                                  "confidence": "medium", "sources": []}]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    # First call: bad shape. Retry: still bad. Fallback to companies=[].
    llm.invoke.return_value = AIMessage(content=json.dumps(bad))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"] == []
