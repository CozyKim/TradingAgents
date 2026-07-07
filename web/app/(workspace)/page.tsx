"use client";
import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { ArrowUpRight, Sparkles } from "lucide-react";

import { MetricCard } from "@/components/dashboard/metric-card";
import { PortfolioSignals } from "@/components/dashboard/portfolio-signals";
import { useHoldings } from "@/hooks/use-holdings";
import { useRunList } from "@/hooks/use-runs";
import { useSchedules } from "@/hooks/use-schedules";
import { getPriceHistory } from "@/lib/prices";
import { RunListItem } from "@/lib/runs";
import { useCurrency, formatPrice } from "@/lib/currency";
import { computePortfolioTotals } from "@/lib/portfolio-totals";
import { useHideBalance } from "@/hooks/use-hide-balance";
import { MASK, maskMoney } from "@/lib/hide-balance";
import { BalanceEyeIcon } from "@/components/dashboard/balance-eye-icon";

export default function DashboardPage() {
  const { data: holdings } = useHoldings();
  const { data: schedules } = useSchedules();
  const { data: runs } = useRunList(
    { page_size: 100 },
    { refetchInterval: 5000, staleTime: 0 },
  );
  const ctx = useCurrency();
  const [prices, setPrices] = useState<Record<string, number | null>>({});

  useEffect(() => {
    if (!holdings?.items) return;
    let cancelled = false;
    (async () => {
      const out: Record<string, number | null> = {};
      await Promise.all(
        holdings.items.map(async (h) => {
          try {
            const r = await getPriceHistory(h.ticker, 5);
            out[h.ticker] = r.last_close;
          } catch {
            out[h.ticker] = null;
          }
        }),
      );
      if (!cancelled) setPrices(out);
    })();
    return () => {
      cancelled = true;
    };
  }, [holdings?.items]);

  // 종목마다 원본 통화가 다르므로(한국=원, 미국=달러) USD 기준으로 정규화해 합산한다.
  // 표시는 fmtMoney가 USD 합계를 현재 표시 통화로 다시 환산한다.
  const totals = useMemo(
    () => computePortfolioTotals(holdings?.items ?? [], prices, ctx.fxRate),
    [holdings?.items, prices, ctx.fxRate],
  );

  const latestByTicker = useMemo(() => {
    const out: Record<string, RunListItem | undefined> = {};
    for (const r of runs?.items ?? []) {
      if (!out[r.ticker]) out[r.ticker] = r;
    }
    return out;
  }, [runs?.items]);

  const runningRuns = (runs?.items ?? []).filter((r) => r.status === "running");

  // totals는 USD 기준 합계이므로 sourceCurrency="USD"로 표시 통화에 맞게 환산한다.
  const fmtMoney = (n: number | null) => formatPrice(n, "USD", ctx);

  const { hidden, revealed, toggle, peek } = useHideBalance();

  const pnlTone =
    totals.pnl == null ? "neutral" : totals.pnl >= 0 ? "pos" : "neg";

  return (
    <div className="mx-auto w-full max-w-screen-md px-4 py-5 md:max-w-screen-xl md:px-8 md:py-8">
      {/* Greeting */}
      <header className="mb-6">
        <p className="text-[13px] font-semibold tracking-[-0.01em] text-text-3">
          오늘의 투자 워크벤치
        </p>
        <h1 className="display mt-1 text-[28px] leading-[1.15] text-text-1 md:text-[34px]">
          좋은 결정을 위한
          <br />
          모든 신호를 한곳에.
        </h1>
      </header>

      {/* Hero portfolio card */}
      <section className="mb-5 overflow-hidden rounded-2xl bg-bg-1 shadow-card">
        <div className="px-5 pt-5 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-[13px] font-semibold text-text-3">
                내 자산
              </span>
              <button
                type="button"
                onClick={toggle}
                aria-pressed={revealed}
                aria-label={revealed ? "자산 금액 숨기기" : "자산 금액 표시"}
                className="inline-flex h-6 w-6 items-center justify-center rounded-md text-text-3 hover:bg-bg-2 hover:text-text-1"
              >
                <BalanceEyeIcon hidden={hidden} className="h-4 w-4" />
              </button>
            </div>
            <Link
              href="/portfolio"
              className="inline-flex items-center gap-0.5 rounded-lg px-2 py-1 text-[12.5px] font-semibold text-text-3 hover:bg-bg-2 hover:text-text-1"
            >
              자세히
              <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2.6} />
            </Link>
          </div>
          <div className="font-num mt-2 text-[36px] font-extrabold leading-none tracking-[-0.035em] text-text-1 md:text-[42px]">
            {hidden ? (
              <button
                type="button"
                onClick={peek}
                data-testid="net-worth"
                aria-label="자산 금액 잠깐 보기"
                className="cursor-pointer tracking-[0.15em] text-text-1"
              >
                {MASK}
              </button>
            ) : (
              <span data-testid="net-worth">{fmtMoney(totals.value)}</span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            {totals.pnl != null ? (
              hidden ? (
                <>
                  <span className="font-num text-[15px] font-bold text-text-3">
                    {MASK}
                  </span>
                  <span className="text-[12.5px] text-text-3">평가손익</span>
                </>
              ) : (
                <>
                  <span
                    className={
                      pnlTone === "pos"
                        ? "font-num text-[15px] font-bold text-signal-buy"
                        : pnlTone === "neg"
                          ? "font-num text-[15px] font-bold text-signal-sell"
                          : "font-num text-[15px] font-bold text-text-2"
                    }
                  >
                    {formatPrice(totals.pnl, "USD", ctx, { signed: true })}
                  </span>
                  {totals.pnlPct != null && (
                    <span
                      className={
                        pnlTone === "pos"
                          ? "font-num text-[13px] font-semibold text-signal-buy"
                          : "font-num text-[13px] font-semibold text-signal-sell"
                      }
                    >
                      ({totals.pnl >= 0 ? "+" : ""}
                      {totals.pnlPct.toFixed(2)}%)
                    </span>
                  )}
                  <span className="text-[12.5px] text-text-3">평가손익</span>
                </>
              )
            ) : (
              <span className="text-[13px] text-text-3">
                실시간 가격을 불러오는 중…
              </span>
            )}
          </div>
        </div>
        <div className="mx-5 my-1 h-px bg-bg-0" />
        <dl className="grid grid-cols-2 gap-px overflow-hidden bg-bg-0">
          <div className="flex flex-col gap-0.5 bg-bg-1 px-5 py-3.5">
            <dt className="text-[12px] font-semibold text-text-3">매입 원가</dt>
            <dd className="font-num text-[15px] font-bold tracking-[-0.02em] text-text-1">
              {maskMoney(hidden, fmtMoney(totals.cost))}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5 bg-bg-1 px-5 py-3.5">
            <dt className="text-[12px] font-semibold text-text-3">
              종목 / 스케줄
            </dt>
            <dd className="font-num text-[15px] font-bold tracking-[-0.02em] text-text-1">
              {totals.positions}
              <span className="text-text-3"> / </span>
              {schedules?.items.length ?? 0}
            </dd>
          </div>
        </dl>
      </section>

      {/* Quick actions */}
      <section className="mb-5 grid grid-cols-2 gap-3">
        <Link
          href="/run"
          className="toss-press flex items-center gap-3 rounded-2xl bg-accent px-4 py-4 text-white shadow-card hover:bg-[#1B64DA]"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/20">
            <Sparkles className="h-5 w-5" strokeWidth={2.4} aria-hidden />
          </div>
          <div className="flex flex-col">
            <span className="text-[12.5px] font-semibold text-white/80">
              지금 시작
            </span>
            <span className="text-[15px] font-bold tracking-[-0.02em]">
              새 분석 실행
            </span>
          </div>
        </Link>
        <Link
          href="/history"
          className="toss-press flex items-center gap-3 rounded-2xl bg-bg-1 px-4 py-4 shadow-card hover:bg-bg-2"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-bg-2">
            <ArrowUpRight
              className="h-5 w-5 text-text-1"
              strokeWidth={2.4}
              aria-hidden
            />
          </div>
          <div className="flex flex-col">
            <span className="text-[12.5px] font-semibold text-text-3">
              지난 분석
            </span>
            <span className="text-[15px] font-bold tracking-[-0.02em] text-text-1">
              분석 기록 보기
            </span>
          </div>
        </Link>
      </section>

      {/* Quick stats — only shown when not in hero (mobile narrow) */}
      <section className="mb-5 hidden grid-cols-3 gap-3 md:grid">
        <MetricCard
          label="평가 자산"
          value={maskMoney(hidden, fmtMoney(totals.value))}
          delta={hidden ? undefined : `매입 ${fmtMoney(totals.cost)}`}
        />
        <MetricCard
          label="평가 손익"
          value={maskMoney(
            hidden,
            formatPrice(totals.pnl, "USD", ctx, { signed: true }),
          )}
          delta={
            hidden || totals.pnlPct == null
              ? undefined
              : `${totals.pnl! >= 0 ? "+" : ""}${totals.pnlPct.toFixed(2)}%`
          }
          tone={hidden ? "neutral" : pnlTone}
        />
        <MetricCard
          label="종목 / 스케줄"
          value={`${totals.positions} / ${schedules?.items.length ?? 0}`}
        />
      </section>

      {/* Holdings signals */}
      <section className="mb-5 rounded-2xl bg-bg-1 shadow-card">
        <header className="flex items-center justify-between px-5 pt-5 pb-2">
          <h2 className="text-[17px] font-bold tracking-[-0.02em] text-text-1">
            보유 종목 시그널
          </h2>
          <Link
            href="/portfolio"
            className="text-[12.5px] font-semibold text-text-3 hover:text-text-1"
          >
            전체보기
          </Link>
        </header>
        <div className="px-5 pb-3">
          <PortfolioSignals
            holdings={holdings?.items ?? []}
            latestByTicker={latestByTicker}
          />
        </div>
      </section>

      {/* Running */}
      <section className="rounded-2xl bg-bg-1 shadow-card">
        <header className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="text-[17px] font-bold tracking-[-0.02em] text-text-1">
            진행 중인 분석
          </h2>
          {runningRuns.length > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-buy/10 px-2 py-0.5 text-[11.5px] font-bold text-signal-buy">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal-buy" />
              {runningRuns.length}건
            </span>
          )}
        </header>
        <div className="px-5 pb-5">
          {runningRuns.length === 0 ? (
            <div className="flex flex-col items-start gap-3 py-1">
              <p className="text-[14px] text-text-2">
                지금 진행 중인 분석이 없어요.
              </p>
              <Link
                href="/run"
                className="inline-flex h-10 items-center gap-1 rounded-xl bg-accent-muted px-4 text-[13px] font-bold text-accent hover:bg-[#D6E7FD]"
              >
                + 새 분석 시작하기
              </Link>
            </div>
          ) : (
            <ul className="-mx-2 flex flex-col">
              {runningRuns.map((r) => (
                <li key={r.run_id}>
                  <Link
                    href={`/run/${r.run_id}`}
                    className="toss-press flex items-center justify-between gap-3 rounded-xl px-2 py-3 hover:bg-bg-2"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-muted text-[13px] font-extrabold tracking-[-0.04em] text-accent">
                        {r.ticker.slice(0, 2)}
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[15px] font-bold tracking-[-0.02em] text-text-1">
                          {r.ticker}
                        </span>
                        <span className="font-num text-[12.5px] text-text-3">
                          {r.analysis_date}
                        </span>
                      </div>
                    </div>
                    <span className="text-[12.5px] font-semibold text-accent">
                      실시간 보기 →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
