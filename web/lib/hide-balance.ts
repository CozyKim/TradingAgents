/** 금액이 가려질 때 표시할 마스크 문자열. */
export const MASK = "••••••";

/**
 * 숨김 상태면 마스크를, 아니면 이미 포맷된 금액 문자열을 그대로 반환한다.
 *
 * Args:
 *   hidden: 현재 금액을 가려야 하는지 여부.
 *   formatted: 이미 통화 포맷된 금액 문자열(예: "₩1,234,000", "—").
 *
 * Returns:
 *   ``hidden``이면 ``MASK``, 아니면 ``formatted`` 원본.
 */
export function maskMoney(hidden: boolean, formatted: string): string {
  return hidden ? MASK : formatted;
}
