"use client";
import * as React from "react";

import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { searchTickers, commitInput, type SearchResult } from "@/lib/ticker-search";
import { cn } from "@/lib/utils";

export type TickerComboboxProps = {
  value: string;
  onChange: (ticker: string) => void;
  onValidityChange?: (valid: boolean) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  className?: string;
};

export function TickerCombobox({
  value,
  onChange,
  onValidityChange,
  placeholder,
  required,
  id,
  disabled,
  autoFocus,
  className,
}: TickerComboboxProps) {
  const [query, setQuery] = React.useState(value);
  // -1 = no explicit navigation yet; user must press ArrowDown/Up or hover to set
  const [highlight, setHighlight] = React.useState(-1);
  const [open, setOpen] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const listboxId = React.useId();

  // 부모가 value를 외부에서 바꾼 경우(예: form reset) query 동기화
  React.useEffect(() => {
    if (value !== query && document.activeElement?.id !== id) {
      setQuery(value);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const results = React.useMemo<SearchResult[]>(() => {
    if (!query.trim()) return [];
    return searchTickers(query);
  }, [query]);

  // 결과가 줄어들었거나 새 query라 무효해진 highlight는 -1로 리셋(자동 선택 방지)
  React.useEffect(() => {
    if (highlight >= results.length) setHighlight(-1);
  }, [results.length, highlight]);

  const setValid = (valid: boolean) => {
    onValidityChange?.(valid);
  };

  const commit = (raw: string): boolean => {
    const result = commitInput(raw);
    if (result.status === "ok") {
      onChange(result.ticker);
      setQuery(result.ticker);
      setError(null);
      setOpen(false);
      setValid(true);
      return true;
    }
    if (result.status === "empty") {
      onChange("");
      setError(null);
      setValid(true);
      return true;
    }
    if (result.status === "needs_selection") {
      setError("목록에서 선택해주세요");
      setValid(false);
      setOpen(true);
      return false;
    }
    setError(
      result.reason === "korean_no_match"
        ? "검색 결과가 없습니다"
        : result.reason === "mixed"
          ? "한글과 영문을 섞어 입력할 수 없습니다"
          : "올바른 영문 티커 형식이 아닙니다",
    );
    setValid(false);
    return false;
  };

  const selectResult = (r: SearchResult) => {
    onChange(r.ticker);
    setQuery(r.ticker);
    setError(null);
    setOpen(false);
    setValid(true);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" && results.length > 0) {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => (h < 0 ? 0 : Math.min(results.length - 1, h + 1)));
      return;
    }
    if (e.key === "ArrowUp" && results.length > 0) {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => (h <= 0 ? results.length - 1 : h - 1));
      return;
    }
    if (e.key === "Enter") {
      // 사용자가 ↑↓로 후보를 명시적으로 선택했을 때만 자동 선택.
      // 그렇지 않으면(highlight=-1) 자유 입력으로 commit 시도.
      if (highlight >= 0 && results[highlight]) {
        e.preventDefault();
        selectResult(results[highlight]);
        return;
      }
      if (!commit(query)) {
        e.preventDefault();
      }
      return;
    }
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
  };

  const onBlur = () => {
    // 옵션 mousedown은 onMouseDown.preventDefault로 blur를 막으므로 이 경로는
    // 옵션 외부로 포커스가 빠지는 경우만 실행된다. open 상태에 의존하지 말고
    // 항상 commit해서 부모 value를 정확히 반영한다.
    commit(query);
  };

  return (
    <Popover open={open && results.length > 0} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div className={cn("relative", className)}>
          <Input
            id={id}
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-activedescendant={results[highlight] ? `${listboxId}-${highlight}` : undefined}
            aria-invalid={error !== null || undefined}
            aria-autocomplete="list"
            autoComplete="off"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setError(null);
              setOpen(true);
              setHighlight(-1); // query 변경 시 stale highlight 리셋(Enter 자동 선택 방지)
              setValid(false); // 사용자가 다시 타이핑 중 — 미확정
            }}
            onFocus={() => results.length > 0 && setOpen(true)}
            onBlur={onBlur}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            required={required}
            disabled={disabled}
            autoFocus={autoFocus}
            className={cn(
              "font-num font-bold uppercase tracking-[-0.02em]",
              error && "ring-1 ring-signal-sell focus-visible:ring-signal-sell",
            )}
          />
          {error && (
            <p className="mt-1 text-xs text-signal-sell" role="alert">
              {error}
            </p>
          )}
        </div>
      </PopoverAnchor>
      <PopoverContent
        id={listboxId}
        role="listbox"
        align="start"
        sideOffset={4}
        className="w-[var(--radix-popover-trigger-width)] p-1"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {results.map((r, i) => (
          <button
            key={`${r.ticker}-${i}`}
            id={`${listboxId}-${i}`}
            role="option"
            aria-selected={i === highlight}
            type="button"
            onMouseEnter={() => setHighlight(i)}
            onMouseDown={(e) => {
              e.preventDefault(); // blur 방지
              selectResult(r);
            }}
            className={cn(
              "flex w-full items-baseline justify-between gap-3 rounded-md px-3 py-2 text-left text-sm",
              i === highlight ? "bg-bg-2" : "hover:bg-bg-2",
            )}
          >
            <span className="font-num font-bold text-text-1">{r.ticker}</span>
            <span className="truncate text-xs text-text-3">
              {r.matched === "ticker" ? r.name : `${r.matchedText} · ${r.name}`}
            </span>
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
