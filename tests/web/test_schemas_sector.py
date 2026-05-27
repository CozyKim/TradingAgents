import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.sector import (
    CompanyShare,
    CandidateTicker,
    SectorCreate,
    SectorReportOut,
)


def test_sector_create_slug_auto_from_name():
    s = SectorCreate(name="My Sector", keywords=["a"])
    assert s.slug == "my-sector"


def test_company_share_basis_enum():
    CompanyShare(name="X", stage="Up", share_value=10.0,
                 share_basis="reported", confidence="high", sources=[])
    with pytest.raises(ValidationError):
        CompanyShare(name="X", stage="Up", share_value=10.0,
                     share_basis="guessed", confidence="high", sources=[])


def test_candidate_ticker_required_fields():
    CandidateTicker(ticker="AAPL", name="Apple", stage="Down", reason="...")
