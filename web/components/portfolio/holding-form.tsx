"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TickerCombobox } from "@/components/ui/ticker-combobox";
import { useCreateHolding } from "@/hooks/use-holdings";

export function HoldingForm({ onCreated }: { onCreated?: () => void }) {
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [avg, setAvg] = useState("");
  const [notes, setNotes] = useState("");
  const m = useCreateHolding();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    m.mutate(
      {
        ticker,
        qty: Number(qty),
        avg_cost: Number(avg),
        notes: notes || undefined,
      },
      {
        onSuccess: () => {
          setTicker("");
          setQty("");
          setAvg("");
          setNotes("");
          onCreated?.();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
      <div>
        <Label htmlFor="ticker">Ticker</Label>
        <TickerCombobox
          id="ticker"
          required
          value={ticker}
          onChange={setTicker}
          placeholder="AAPL or 애플"
        />
      </div>
      <div>
        <Label htmlFor="qty">Quantity</Label>
        <Input
          id="qty"
          type="number"
          step="any"
          min="0"
          required
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="avg">Avg cost</Label>
        <Input
          id="avg"
          type="number"
          step="any"
          min="0"
          required
          value={avg}
          onChange={(e) => setAvg(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="notes">Notes</Label>
        <Input
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="optional"
        />
      </div>
      <Button type="submit" disabled={m.isPending}>
        {m.isPending ? "Adding…" : "Add"}
      </Button>
      {m.error ? (
        <p className="text-xs text-neg col-span-full">{(m.error as Error).message}</p>
      ) : null}
    </form>
  );
}
