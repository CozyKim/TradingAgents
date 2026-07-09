/**
 * 종목명(주역)과 티커(보조)를 한 줄로 표시한다.
 *
 * 이름이 없으면 — 아직 도착하지 않았거나, 해석에 실패했거나(지수 등) — 티커만
 * 주역 자리에 굵게 표시한다. 이름이 도착하면 앞에 삽입되며 짧은 레이아웃 시프트가
 * 생기는데, 이는 수용하기로 한 트레이드오프다.
 *
 * 데이터를 스스로 가져오지 않는다. 행마다 훅을 호출하면 N개 요청이 되므로
 * 페이지가 useTickerNames 로 맵을 얻어 name 을 prop 으로 내린다.
 */
export function TickerLabel({
  ticker,
  name,
  className = "",
  nameClassName = "font-medium",
}: {
  ticker: string;
  name?: string;
  className?: string;
  nameClassName?: string;
}) {
  if (!name) {
    return <span className={`font-mono ${nameClassName} ${className}`}>{ticker}</span>;
  }
  return (
    <span className={`inline-flex min-w-0 items-baseline gap-1.5 ${className}`}>
      <span className={`truncate ${nameClassName}`}>{name}</span>
      <span className="shrink-0 font-mono text-xs text-text-3">{ticker}</span>
    </span>
  );
}
