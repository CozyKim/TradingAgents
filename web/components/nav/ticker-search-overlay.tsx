"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { useTickerSearch } from "@/hooks/use-ticker-search";
import { resolveMarket } from "@/lib/ticker-market";
import { commitInput } from "@/lib/ticker-search";

type Props = {
  open: boolean;
  /** popstate가 도착했을 때만 호출된다. 닫기 버튼/Escape는 history.back()을 거친다. */
  onClose: () => void;
  /** 닫을 때 포커스를 되돌릴 요소(돋보기 버튼). 결과 선택으로 페이지가 바뀔 때는 복원하지 않는다. */
  restoreFocusRef?: React.RefObject<HTMLElement | null>;
};

/**
 * 전체화면 티커 검색.
 *
 * 라우트가 아니라 로컬 state이므로, 안드로이드 뒤로가기를 지원하려면 여는 쪽에서
 * history.pushState로 더미 엔트리를 쌓아야 한다(MobileTopBar가 한다). 닫기는 항상
 * history.back()으로 그 엔트리를 소비하고, 결과 선택은 router.replace로 더미를
 * 상세 페이지로 치환한다 — push였다면 상세에서 뒤로가기를 두 번 눌러야 하고
 * 첫 번째는 화면이 안 바뀌어 고장으로 보인다.
 */
export function TickerSearchOverlay({ open, onClose, restoreFocusRef }: Props) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const listboxId = React.useId();
  // 결과 선택으로 페이지가 바뀌는 경우 — 닫힘 전이에서 포커스 복원을 건너뛴다.
  const navigatingRef = React.useRef(false);
  const prevOpenRef = React.useRef(open);

  // 닫혀 있으면 빈 질의를 넘겨 원격 검색이 돌지 않게 한다.
  const { results, loading, showEmptyHint } = useTickerSearch(open ? query : "");

  // md(768px) 이상에선 오버레이가 md:hidden으로 사라지므로, 그 상태에선 body 스크롤도
  // 잠그지 않는다. 세로→가로 회전으로 뷰포트가 넓어지면 잠금이 풀려야 한다.
  const [isDesktop, setIsDesktop] = React.useState(false);
  React.useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  React.useEffect(() => {
    if (!open) return;
    setQuery("");
    setError(null);
  }, [open]);

  // 닫힘 전이(open true→false)에 돋보기 버튼으로 포커스를 되돌린다.
  // 단, 결과 선택으로 페이지가 바뀌는 경우(navigatingRef)는 새 페이지로 넘어가므로 건너뛴다.
  React.useEffect(() => {
    const was = prevOpenRef.current;
    prevOpenRef.current = open;
    if (was && !open) {
      if (navigatingRef.current) {
        navigatingRef.current = false;
      } else {
        restoreFocusRef?.current?.focus();
      }
    }
  }, [open, restoreFocusRef]);

  React.useEffect(() => {
    if (!open) return;
    const onPop = () => onClose();
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [open, onClose]);

  React.useEffect(() => {
    if (!open || isDesktop) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open, isDesktop]);

  // 더미 히스토리 엔트리를 반드시 소비한다. onClose를 직접 부르면 엔트리가 남는다.
  const requestClose = React.useCallback(() => {
    window.history.back();
  }, []);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") requestClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, requestClose]);

  const navigate = (ticker: string) => {
    // open=false 로 인한 effect cleanup이 popstate 리스너를 뗀다.
    // router.replace는 popstate를 발생시키지 않으므로 경합이 없다.
    // 페이지가 바뀌므로 닫힘 전이에서 돋보기로 포커스를 되돌리지 않는다.
    navigatingRef.current = true;
    onClose();
    router.replace(`/portfolio/${encodeURIComponent(ticker)}`);
  };

  const submitQuery = () => {
    const result = commitInput(query);
    if (result.status === "ok") {
      navigate(result.ticker);
      return;
    }
    if (result.status === "empty") return;
    if (result.status === "needs_selection") {
      setError("목록에서 선택해주세요");
      return;
    }
    setError(
      result.reason === "korean_no_match"
        ? "검색 결과가 없습니다"
        : result.reason === "mixed"
          ? "한글과 영문을 섞어 입력할 수 없습니다"
          : "올바른 영문 티커 형식이 아닙니다",
    );
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="티커 검색"
      className="md:hidden fixed inset-0 z-50 flex flex-col bg-bg-0 pb-[env(safe-area-inset-bottom)]"
    >
      <div className="flex h-14 shrink-0 items-center gap-2 px-3">
        <button
          type="button"
          aria-label="검색 닫기"
          onClick={requestClose}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-text-2 hover:text-text-1"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
        <Input
          role="combobox"
          aria-expanded
          aria-controls={listboxId}
          aria-autocomplete="list"
          autoComplete="off"
          autoFocus
          value={query}
          placeholder="티커 또는 회사명 (예: AAPL, 삼성전자)"
          onChange={(e) => {
            setQuery(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submitQuery();
            }
          }}
          className="flex-1"
        />
      </div>

      {error && (
        <p role="alert" className="px-4 pb-2 text-xs text-signal-sell">
          {error}
        </p>
      )}

      <div
        id={listboxId}
        role="listbox"
        aria-label="검색 결과"
        className="flex-1 overflow-y-auto px-2 pb-4"
      >
        {results.map((r, i) => {
          const badge = resolveMarket(r.ticker);
          return (
            <button
              key={`${r.ticker}-${i}`}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => navigate(r.ticker)}
              className="flex w-full items-baseline justify-between gap-3 rounded-md px-3 py-3 text-left hover:bg-bg-2"
            >
              <span className="flex shrink-0 items-baseline gap-1.5">
                {badge && (
                  <span role="img" aria-label={badge.aria} title={badge.aria}>
                    {badge.emoji}
                  </span>
                )}
                <span className="font-num font-bold text-text-1">{r.ticker}</span>
              </span>
              <span className="truncate text-xs text-text-3">{r.name}</span>
            </button>
          );
        })}

        {loading && results.length === 0 && (
          <div className="px-3 py-3 text-xs text-text-3" role="status">
            검색 중…
          </div>
        )}

        {showEmptyHint && (
          <div className="px-3 py-3 text-xs text-text-3" role="status">
            검색 결과가 없습니다 · 영문 회사명이나 티커로 검색해 보세요
          </div>
        )}
      </div>
    </div>
  );
}
