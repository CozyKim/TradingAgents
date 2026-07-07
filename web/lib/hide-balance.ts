import { cn } from "@/lib/utils";

/**
 * 숨김 상태의 금액 요소에 붙일 클래스.
 *
 * ``hidden``이면 실제 금액을 강한 CSS 블러(대략적인 금액·자릿수도 유추하기
 * 어려운 수준)로 흐리게 하고 살짝 축소하며 텍스트 선택을 막는다. filter와
 * transform 전환을 항상 포함하므로, 노출/숨김이 "초점이 맞춰지듯" 부드럽고
 * 인터랙티브하게 애니메이션된다.
 *
 * Args:
 *   hidden: 현재 금액을 가려야 하는지 여부.
 *
 * Returns:
 *   Tailwind 클래스 문자열(노출 시 전환 클래스만, 숨김 시 블러·축소 포함).
 */
export function balanceBlurClass(hidden: boolean): string {
  return cn(
    "origin-left transition-[filter,transform] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
    hidden && "blur-[12px] select-none scale-[0.97]",
  );
}
