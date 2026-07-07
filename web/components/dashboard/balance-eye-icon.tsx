/**
 * 자산 숨김 토글용 눈 아이콘.
 *
 * ``hidden``이면 가려진(감은) 눈, 아니면 열린 눈을 그린다.
 * path d 값은 codex가 다듬은 값으로 교체 가능(스타일은 유지).
 */
export function BalanceEyeIcon({
  hidden,
  className,
}: {
  hidden: boolean;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {hidden ? (
        <>
          <path d="M4 10c2.1 3.2 5 4.8 8 4.8s5.9-1.6 8-4.8" />
          <path d="M8.2 13.2 7 15" />
          <path d="M15.8 13.2 17 15" />
        </>
      ) : (
        <>
          <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
        </>
      )}
    </svg>
  );
}
