export interface SignalMarker {
  date: string;
  decision: "BUY" | "SELL" | "HOLD" | "OVERWEIGHT" | "UNDERWEIGHT";
  close: number;
}
