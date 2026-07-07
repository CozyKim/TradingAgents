"""Unit tests for ticker search market-classification and normalization."""
from tradingagents_web.services.ticker_search import (
    _classify_market,
    _normalize_naver_item,
    _normalize_yahoo_quote,
)


def test_classify_market_us_kr_global():
    assert _classify_market("AAPL") == "US"
    assert _classify_market("BRK.B") == "US"          # 클래스주도 US
    assert _classify_market("005930.KS") == "KR"
    assert _classify_market("035720.KQ") == "KR"
    assert _classify_market("7203.T") is None          # 도쿄 → 제외
    assert _classify_market("") is None


def test_normalize_yahoo_equity_and_etf():
    us = _normalize_yahoo_quote(
        {"symbol": "NVDA", "shortname": "NVIDIA Corporation", "quoteType": "EQUITY", "exchange": "NMS"}
    )
    assert us is not None
    assert (us.ticker, us.name, us.market) == ("NVDA", "NVIDIA Corporation", "US")

    etf = _normalize_yahoo_quote(
        {"symbol": "QQQ", "shortname": "Invesco QQQ Trust", "quoteType": "ETF", "exchange": "NMS"}
    )
    assert etf is not None and etf.market == "US"

    kr = _normalize_yahoo_quote(
        {"symbol": "005930.KS", "shortname": "SamsungElec", "quoteType": "EQUITY", "exchange": "KSC"}
    )
    assert kr is not None and kr.market == "KR"


def test_normalize_yahoo_rejects_noise():
    assert _normalize_yahoo_quote({"symbol": "^GSPC", "quoteType": "INDEX"}) is None
    assert _normalize_yahoo_quote({"symbol": "BTC-USD", "quoteType": "CRYPTOCURRENCY"}) is None
    assert _normalize_yahoo_quote(
        {"symbol": "NVD.DE", "shortname": "NVIDIA", "quoteType": "EQUITY", "exchange": "GER"}
    ) is None  # 글로벌 접미사 → 제외


def test_normalize_naver_kospi_kosdaq_us():
    kospi = _normalize_naver_item(
        {"code": "005930", "name": "삼성전자", "typeCode": "KOSPI", "nationCode": "KOR"}
    )
    assert kospi is not None and (kospi.ticker, kospi.market) == ("005930.KS", "KR")

    kosdaq = _normalize_naver_item(
        {"code": "035720", "name": "카카오", "typeCode": "KOSDAQ", "nationCode": "KOR"}
    )
    assert kosdaq is not None and kosdaq.ticker == "035720.KQ"

    us = _normalize_naver_item(
        {"code": "SBUX", "name": "스타벅스", "typeCode": "NASDAQ", "nationCode": "USA"}
    )
    assert us is not None and (us.ticker, us.market) == ("SBUX", "US")


def test_normalize_naver_rejects_derivatives_and_other_nations():
    assert _normalize_naver_item(
        {"code": "0193W0", "name": "KODEX 삼성전자단일종목레버리지", "typeCode": "KOSPI", "nationCode": "KOR"}
    ) is None
    assert _normalize_naver_item(
        {"code": "04337", "name": "스타벅스", "typeCode": "HONG_KONG", "nationCode": "HKG"}
    ) is None
