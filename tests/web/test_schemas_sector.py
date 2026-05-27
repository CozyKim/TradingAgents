import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.sector import (
    CandidateTicker,
    CompanyShare,
    SectorCreate,
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


def test_sector_create_long_name_slug_truncated_to_db_limit():
    # Names up to 128 chars are allowed; the derived slug must fit in 64.
    s = SectorCreate(name="a" * 128)
    assert s.slug is not None
    assert 1 <= len(s.slug) <= 64


def test_sector_create_explicit_long_slug_rejected():
    with pytest.raises(ValidationError):
        SectorCreate(name="ok", slug="x" * 65)


def test_sector_create_explicit_empty_slug_rejected():
    with pytest.raises(ValidationError):
        SectorCreate(name="ok", slug="")
