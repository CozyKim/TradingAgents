"""Tests for the Naver 종목토론방 social-sentiment vendor (Korean tickers)."""

import unittest
from unittest.mock import MagicMock, patch

from tradingagents.dataflows import naver_finance_board as nfb


def _post_row(
    date: str, title: str, views: int, nid: int = 1, agree: int = 1
) -> str:
    """Build one 종목토론방 table row mirroring the live column layout.

    Columns (left→right): date · title(link) · author · views · agree · disagree.
    On the live page the ``tah p10`` class sits on the inner ``<span>``/``<strong>``
    (the ``<td>`` itself has no class), and the date and view cells look alike —
    so the vendor reads the first bare-int cell as views and the second as agree.
    """
    return (
        '<tr onmouseover="x" onmouseout="y">'
        f'<td><span class="tah p10 gray03">{date}</span></td>'
        f'<td class="title"><a href="/item/board_read.naver?code=005930&nid={nid}&page=1"'
        f' title="{title}">disp</a></td>'
        '<td class="p11 align_right"><a href="#">user</a></td>'
        f'<td><span class="tah p10 gray03">{views}</span></td>'
        f'<td><strong class="tah p10 red01">{agree}</strong></td>'
        '<td><strong class="tah p10 gray03 ">0</strong></td>'
        "</tr>"
    )


def _board(*rows: str) -> str:
    return "<html><body><table summary='종목토론'>" + "".join(rows) + "</table></body></html>"


def _mock_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    # finance.naver.com serves UTF-8 (Content-Type: text/html;charset=UTF-8).
    resp.content = text.encode("utf-8")
    return resp


class ExtractKrxCodeTests(unittest.TestCase):
    def test_strips_ks_suffix(self):
        self.assertEqual(nfb._extract_krx_code("005930.KS"), "005930")

    def test_strips_kq_suffix_case_insensitive(self):
        self.assertEqual(nfb._extract_krx_code("035720.kq"), "035720")

    def test_returns_none_for_non_korean_ticker(self):
        self.assertIsNone(nfb._extract_krx_code("AAPL"))

    def test_returns_none_when_code_not_six_digits(self):
        self.assertIsNone(nfb._extract_krx_code("ABC.KS"))


class GetSocialMessagesNaverTests(unittest.TestCase):
    """Naver 종목토론방 as the Korean counterpart of StockTwits get_social_messages."""

    _BOARD = _board(
        _post_row("2026.05.30 12:34", "삼성전자 신고가 가즈아", 50, nid=111, agree=2),
        _post_row("2026.05.30 09:10", "실적 어닝 서프라이즈 기대", 200, nid=110, agree=9),
    )

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_renders_title_views_and_agree(self, mock_get):
        mock_get.return_value = _mock_response(200, self._BOARD)
        result = nfb.get_social_messages_naver("005930.KS", limit=10)
        self.assertIn("005930", result)
        self.assertIn("삼성전자 신고가 가즈아", result)
        self.assertIn("조회", result)
        self.assertIn("추천", result)
        self.assertIn("200", result)  # view count surfaced
        self.assertIn("9", result)  # agree count surfaced

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_default_sort_is_views(self, mock_get):
        # 종목토론방 is a Korean retail board — the default/forced sort is 조회순.
        mock_get.return_value = _mock_response(200, self._BOARD)
        result = nfb.get_social_messages_naver("005930.KS", limit=10)
        # No sort given → most-viewed first: 200-view post before 50-view post.
        self.assertLess(
            result.index("실적 어닝 서프라이즈 기대"),
            result.index("삼성전자 신고가 가즈아"),
        )

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_sort_views_orders_by_view_count(self, mock_get):
        mock_get.return_value = _mock_response(200, self._BOARD)
        result = nfb.get_social_messages_naver("005930.KS", limit=10, sort="views")
        # 200-view post ranks above the 50-view post.
        self.assertLess(
            result.index("실적 어닝 서프라이즈 기대"),
            result.index("삼성전자 신고가 가즈아"),
        )

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_explicit_latest_keeps_board_order(self, mock_get):
        # Only an explicit 'latest' opts out of 조회순 → board (newest-first) order.
        mock_get.return_value = _mock_response(200, self._BOARD)
        result = nfb.get_social_messages_naver("005930.KS", limit=10, sort="latest")
        self.assertLess(
            result.index("삼성전자 신고가 가즈아"),
            result.index("실적 어닝 서프라이즈 기대"),
        )

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_non_latest_sort_values_coerce_to_views(self, mock_get):
        # Anything that is not exactly 'latest' (typos, 한국어, casing, spacing)
        # falls back to 조회순 instead of silently rendering newest-first — this
        # is the "조회수 우선이랬는데 최신순" bug guard.
        mock_get.return_value = _mock_response(200, self._BOARD)
        for value in ("Views", " views ", "조회순", "popular", "by_views"):
            result = nfb.get_social_messages_naver("005930.KS", limit=10, sort=value)
            self.assertLess(
                result.index("실적 어닝 서프라이즈 기대"),
                result.index("삼성전자 신고가 가즈아"),
                msg=f"sort={value!r} should sort by view count",
            )
            self.assertIn("by view count", result)

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_limit_caps_message_count(self, mock_get):
        rows = [
            _post_row(f"2026.05.30 10:{i:02d}", f"글{i}", 10 + i, nid=i)
            for i in range(8)
        ]
        mock_get.return_value = _mock_response(200, _board(*rows))
        result = nfb.get_social_messages_naver("005930.KS", limit=3)
        self.assertEqual(result.count("\n- "), 3)

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_days_filters_recent_window_then_sorts_by_views(self, mock_get):
        # Window is anchored to the newest post (06-01), so days=3 keeps
        # 05-30..06-01 and drops 05-28 — even though 05-28 has the most views.
        board = _board(
            _post_row("2026.06.01 10:00", "오늘글", 10, nid=1),
            _post_row("2026.05.30 09:00", "사흘전글", 999, nid=2),
            _post_row("2026.05.28 09:00", "닷새전글", 5000, nid=3),
        )
        mock_get.return_value = _mock_response(200, board)
        result = nfb.get_social_messages_naver(
            "005930.KS", limit=10, sort="views", days=3
        )
        self.assertIn("오늘글", result)
        self.assertIn("사흘전글", result)
        self.assertNotIn("닷새전글", result)  # outside the 3-day window
        # Within the window, most-viewed first: 사흘전글(999) before 오늘글(10).
        self.assertLess(result.index("사흘전글"), result.index("오늘글"))

    def test_non_korean_ticker_returns_explicit_message(self):
        result = nfb.get_social_messages_naver("AAPL", limit=10)
        self.assertIn("not a Korean", result)

    @patch("tradingagents.dataflows.naver_finance_board.requests.get")
    def test_network_error_returns_readable_string(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("boom")
        result = nfb.get_social_messages_naver("005930.KS", limit=10)
        self.assertIn("Error", result)
        self.assertIn("005930", result)


if __name__ == "__main__":
    unittest.main()
