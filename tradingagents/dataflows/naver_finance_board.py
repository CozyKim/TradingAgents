"""Naver 종목토론방 vendor: retail-investor sentiment source for Korean tickers.

Finnhub's free tier returns HTTP 403 for non-US symbols, so Korean tickers
(``005930.KS`` / ``035720.KQ``) have no social-sentiment coverage there. Naver
Finance's 종목토론방 is the de-facto public Korean retail board; this vendor
scrapes recent post titles so the analyst LLM can derive sentiment itself
(the board exposes no sentiment score — text only).

Politeness / risk notes (the board has no official API):
- Single low-frequency GET per call (one page), browser-like User-Agent.
- Page is UTF-8 encoded (Content-Type: text/html;charset=UTF-8).
- Respect robots.txt / 이용약관; keep volume low and cache upstream. Production
  use of this source carries blocking and legal risk — see project docs.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import requests

BOARD_URL = "https://finance.naver.com/item/board.naver"
_TIMEOUT_SECONDS = 10
_DEFAULT_MAX_ITEMS = 30
# Naver serves bot-default UAs a challenge/redirect; mimic a real browser.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

# A 종목토론방 row links to ``board_read.naver`` and carries the full post text
# in the anchor's ``title`` attribute; the same row holds a ``yyyy.mm.dd hh:mm``
# stamp. Keying off these two signals is more robust than column positions.
_ROW_SPLIT_RE = re.compile(r"<tr[\s>]", re.IGNORECASE)
_TITLE_RE = re.compile(
    r'href="[^"]*board_read\.naver[^"]*"[^>]*\btitle="([^"]*)"',
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\s+\d{2}:\d{2}")
# Date/views/agree/disagree all render as an inner <span>/<strong class="tah
# p10 …">N</…> (the <td> itself has no class). The view count is the row's first
# such cell holding a bare integer — the date cell shares the class but its value
# (yyyy.mm.dd …) is never a bare int, so it is skipped naturally.
_NUMERIC_CELL_RE = re.compile(r'class="tah p10[^"]*"[^>]*>\s*(\d+)\s*<')
_MAX_PAGES = 10

_log = logging.getLogger(__name__)


def _extract_counts(row: str) -> tuple[int, int]:
    """Return ``(views, agree)`` — the first two bare-integer ``tah p10`` cells.

    Row cells run date · title · author · views · agree · disagree; the date
    cell is never a bare int, so the first two integers are views then agree
    (the 추천/공감 count, used as a Korean analogue of StockTwits' bull/bear tag).
    """
    nums: list[int] = []
    for cell in row.split("<td")[1:]:
        m = _NUMERIC_CELL_RE.search(cell)
        if m:
            nums.append(int(m.group(1)))
            if len(nums) >= 2:
                break
    views = nums[0] if nums else 0
    agree = nums[1] if len(nums) > 1 else 0
    return views, agree


def _extract_krx_code(ticker: str) -> str | None:
    """Return the bare 6-digit KRX code for a ``.KS``/``.KQ`` ticker, else None.

    Args:
        ticker: A ticker possibly suffixed with a Korean exchange code, e.g.
            ``"005930.KS"`` (KOSPI) or ``"035720.KQ"`` (KOSDAQ).

    Returns:
        The 6-digit numeric code (``"005930"``) when ``ticker`` is a Korean
        symbol, otherwise ``None``.
    """
    upper = ticker.strip().upper()
    if not upper.endswith((".KS", ".KQ")):
        return None
    code = upper[:-3]
    return code if re.fullmatch(r"\d{6}", code) else None


def _parse_messages_page(html: str) -> list[tuple[str, str, int, int]]:
    """Parse one board page into ``(date, title, views, agree)`` rows, newest first."""
    out: list[tuple[str, str, int, int]] = []
    for row in _ROW_SPLIT_RE.split(html):
        title_match = _TITLE_RE.search(row)
        date_match = _DATE_RE.search(row)
        if not title_match or not date_match:
            continue
        title = title_match.group(1).strip()
        if not title:
            continue
        post_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        views, agree = _extract_counts(row)
        out.append((post_date, title, views, agree))
    return out


def get_social_messages_naver(
    ticker: str,
    limit: int = _DEFAULT_MAX_ITEMS,
    sort: str = "latest",
    days: int | None = None,
    max_pages: int = 5,
) -> str:
    """Fetch recent 종목토론방 posts for a Korean ticker (StockTwits counterpart).

    This is the Korean analogue of the StockTwits ``get_social_messages`` vendor:
    individual retail-investor posts rather than news. Each line carries the post
    title (which is itself the message on this board), view count, and 추천 count.

    Args:
        ticker: Korean ticker, e.g. ``"005930.KS"`` or ``"035720.KQ"``.
        limit: Maximum posts to render (default 30). Clamped to [1, 50].
        sort: ``"latest"`` (default, newest first) or ``"views"`` (most-viewed
            first within the scanned/​windowed set).
        days: When set, keep only posts within the last ``days`` days, anchored
            to the newest post seen (the board is near-real-time, so this is
            effectively "last N days"). ``None`` (default) applies no window.
        max_pages: Pages to scan (default 5). Clamped to [1, 10]. Stops early
            once a page falls below the window, or once ``limit`` newest posts
            are collected when neither ``days`` nor ``sort='views'`` is set.

    Returns:
        A markdown string. On a non-Korean ticker, network error, or non-200
        response (with nothing collected), returns a user-visible explanation
        string (never raises) — there is no fallback vendor for Korean stocks.
    """
    code = _extract_krx_code(ticker)
    if code is None:
        return (
            f"{ticker} is not a Korean ticker (.KS/.KQ); "
            "Naver 종목토론방 messages are unavailable."
        )

    capped = max(1, min(int(limit), 50))
    pages = max(1, min(int(max_pages), _MAX_PAGES))

    posts: list[tuple[str, str, int, int]] = []
    cutoff: str | None = None
    for page in range(1, pages + 1):
        try:
            resp = requests.get(
                BOARD_URL,
                params={"code": code, "page": page},
                headers=_HEADERS,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            _log.warning("naver board network error for %s p%s: %s", code, page, exc)
            if posts:
                break
            return f"Error fetching 종목토론방 for {code}: {exc}"

        if resp.status_code != 200:
            _log.warning("naver board HTTP %s for %s p%s", resp.status_code, code, page)
            if posts:
                break
            return (
                f"Naver 종목토론방 request failed (HTTP {resp.status_code}) for {code}."
            )

        page_posts = _parse_messages_page(resp.content.decode("utf-8", errors="replace"))
        if not page_posts:
            break  # end of board
        posts.extend(page_posts)
        if days and cutoff is None:
            newest = max(p[0] for p in posts)
            cutoff = (date.fromisoformat(newest) - timedelta(days=days - 1)).isoformat()
        if cutoff is not None and min(p[0] for p in page_posts) < cutoff:
            break  # page crossed below the window → older pages can't help
        if sort == "latest" and not days and len(posts) >= capped:
            break  # newest-first only needs the first `limit` posts

    if not posts:
        return f"No 종목토론방 posts for {code}."

    if cutoff is not None:
        posts = [p for p in posts if p[0] >= cutoff]
        if not posts:
            return f"No 종목토론방 posts for {code} in the last {days} day(s)."

    if sort == "views":
        posts = sorted(posts, key=lambda p: p[2], reverse=True)
    selected = posts[:capped]

    window = f", last {days}d" if days else ""
    sort_label = "by view count" if sort == "views" else "newest first"
    parts = [
        f"## 종목토론방 — {code} (last {len(selected)} posts, {sort_label}{window})",
        "",
    ]
    for post_date, title, views, agree in selected:
        parts.append(f"- [{post_date}] (조회 {views}, 추천 {agree}) {title}")
    return "\n".join(parts).rstrip() + "\n"
