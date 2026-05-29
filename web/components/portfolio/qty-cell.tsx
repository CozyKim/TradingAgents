"use client";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { useUpdateHolding } from "@/hooks/use-holdings";
import { useCurrency, formatPrice } from "@/lib/currency";
import type { HoldingUpdatePayload } from "@/lib/holdings";

/**
 * holding의 숫자 필드(qty/avg_cost)를 인라인 편집하는 범용 셀.
 * 클릭하면 입력 필드로 전환되고, Enter 또는 포커스 아웃 시 저장, Escape로 취소한다.
 */
function EditableNumberCell({
  holdingId,
  field,
  value,
  display,
  title,
  className,
}: {
  holdingId: number;
  /** PATCH payload에 들어갈 필드명 */
  field: "qty" | "avg_cost";
  /** 편집 대상이 되는 원본 숫자 값(저장되는 실제 값) */
  value: number;
  /** 비편집 상태에서 보여줄 표시 문자열 (기본: 원본 값) */
  display?: string;
  /** 편집 가능 버튼의 마우스오버 안내 */
  title?: string;
  /** 비편집 버튼에 추가로 적용할 클래스 */
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));
  const m = useUpdateHolding();

  const commit = () => {
    const next = Number(draft);
    // 빈 값·음수·NaN 등 유효하지 않으면 원래 값으로 되돌리고 편집 종료
    if (draft.trim() === "" || !Number.isFinite(next) || next < 0) {
      setDraft(String(value));
      setEditing(false);
      return;
    }
    if (next !== value) {
      m.mutate({ id: holdingId, payload: { [field]: next } as HoldingUpdatePayload });
    }
    setEditing(false);
  };

  const cancel = () => {
    setDraft(String(value));
    setEditing(false);
  };

  if (editing) {
    return (
      <Input
        type="number"
        step="any"
        min="0"
        autoFocus
        disabled={m.isPending}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          else if (e.key === "Escape") cancel();
        }}
        className="h-8 w-24 px-2 text-right text-sm"
      />
    );
  }

  return (
    <button
      type="button"
      title={title ?? "클릭하여 수정"}
      onClick={() => {
        setDraft(String(value));
        setEditing(true);
      }}
      className={
        "font-mono tabular-nums rounded px-1 -mx-1 hover:bg-bg-2 hover:underline cursor-pointer " +
        (className ?? "")
      }
    >
      {display ?? value}
    </button>
  );
}

export function QtyCell({
  holdingId,
  qty,
  className,
}: {
  holdingId: number;
  qty: number;
  className?: string;
}) {
  return (
    <EditableNumberCell
      holdingId={holdingId}
      field="qty"
      value={qty}
      title="클릭하여 수량 수정"
      className={className}
    />
  );
}

export function AvgCostCell({
  holdingId,
  avgCost,
  className,
}: {
  holdingId: number;
  avgCost: number;
  className?: string;
}) {
  const ctx = useCurrency();
  // avg_cost는 USD로 저장되고 표시할 때만 환율 변환된다.
  // 편집 input에는 USD 원본 값을 노출/저장하므로 안내 문구에 'USD 기준'을 명시한다.
  return (
    <EditableNumberCell
      holdingId={holdingId}
      field="avg_cost"
      value={avgCost}
      display={formatPrice(avgCost, ctx)}
      title="클릭하여 평단가 수정 (USD 기준)"
      className={className}
    />
  );
}
