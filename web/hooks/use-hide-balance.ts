import { useCallback, useEffect, useRef, useState } from "react";

/** peek(미리보기)가 자동으로 다시 숨겨지기까지의 시간(ms). */
export const PEEK_MS = 3000;

export interface UseHideBalance {
  /** 현재 금액이 가려져 있는지. */
  hidden: boolean;
  /** 세션 토글이 켜져 있는지(눈 버튼 aria-pressed용). */
  revealed: boolean;
  /** 세션 토글 반전(다음 새로고침 시 리셋). */
  toggle: () => void;
  /** 잠깐 미리보기: PEEK_MS 동안 노출 후 자동 숨김. */
  peek: () => void;
}

/**
 * 메인 대시보드 요약 금액의 숨김 상태를 관리한다.
 *
 * 영속화하지 않으므로 매 마운트(접속/새로고침)마다 숨김으로 시작한다.
 * ``revealed``(토글)와 ``peeking``(임시 노출) 중 하나라도 참이면 노출한다.
 */
export function useHideBalance(): UseHideBalance {
  const [revealed, setRevealed] = useState(false);
  const [peeking, setPeeking] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current != null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const toggle = useCallback(() => {
    clearTimer();
    setPeeking(false);
    setRevealed((v) => !v);
  }, [clearTimer]);

  const peek = useCallback(() => {
    clearTimer();
    setPeeking(true);
    timerRef.current = setTimeout(() => {
      setPeeking(false);
      timerRef.current = null;
    }, PEEK_MS);
  }, [clearTimer]);

  // 언마운트 시 남은 타이머 정리(메모리 누수 방지).
  useEffect(() => clearTimer, [clearTimer]);

  return { hidden: !(revealed || peeking), revealed, toggle, peek };
}
