import { cn } from "@/lib/utils";

/**
 * 숨김 상태의 금액 요소에 붙일 클래스.
 *
 * ``hidden``이면 실제 금액을 CSS 블러로 흐리게 하고 텍스트 선택을 막는다.
 * 항상 filter 전환을 포함하므로 노출/숨김 전환이 부드럽게 애니메이션된다.
 *
 * Args:
 *   hidden: 현재 금액을 가려야 하는지 여부.
 *
 * Returns:
 *   Tailwind 클래스 문자열(노출 시 전환 클래스만, 숨김 시 블러 포함).
 */
export function balanceBlurClass(hidden: boolean): string {
  return cn(
    "transition-[filter] duration-200",
    hidden && "blur-[6px] select-none",
  );
}
