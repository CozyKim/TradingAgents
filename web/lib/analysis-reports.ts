export const REPORT_FIELDS = [
  ["market_report", "Market"],
  ["sentiment_report", "Sentiment"],
  ["news_report", "News"],
  ["fundamentals_report", "Fundamentals"],
  ["investment_plan", "Researcher Verdict"],
  ["trader_investment_plan", "Trader Plan"],
  ["final_trade_decision", "Final Decision"],
] as const;

export interface ReportSection {
  key: string;
  label: string;
  value: string;
}

export function getReportSections(
  finalState: Record<string, unknown> | null,
): ReportSection[] {
  const state = finalState ?? {};
  return REPORT_FIELDS.flatMap(([key, label]) => {
    const value = state[key];
    if (typeof value !== "string" || value.trim().length === 0) {
      return [];
    }
    return [{ key, label, value }];
  });
}
