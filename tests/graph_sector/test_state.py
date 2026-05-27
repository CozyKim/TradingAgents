from tradingagents.graph_sector.state import SectorState


def test_default_init_has_empty_companies():
    s = SectorState(sector_slug="ai", sector_name="AI", keywords=["GPU"])
    assert s.companies == []
    assert s.candidate_tickers == []
    assert s.budget.total == 12
    assert s.budget.per_node == 3


def test_override_budget_from_env(monkeypatch):
    monkeypatch.setenv("SECTOR_SEARCH_BUDGET", "20")
    monkeypatch.setenv("SECTOR_NODE_SEARCH_BUDGET", "5")
    s = SectorState.from_request(
        sector_slug="x", sector_name="X", keywords=[]
    )
    assert s.budget.total == 20
    assert s.budget.per_node == 5
