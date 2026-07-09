import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HoldingForm } from "../holding-form";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("@/hooks/use-holdings", () => ({
  useCreateHolding: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  }),
}));

vi.mock("@/components/ui/ticker-combobox", () => ({
  TickerCombobox: ({
    id,
    value,
    onChange,
    placeholder,
  }: {
    id?: string;
    value: string;
    onChange: (ticker: string) => void;
    placeholder?: string;
  }) => (
    <div>
      <input id={id} value={value} placeholder={placeholder} readOnly />
      <button type="button" onClick={() => onChange("005930.KS")}>
        Select Korean ticker
      </button>
    </div>
  ),
}));

let roots: Root[] = [];
let containers: HTMLDivElement[] = [];

function render(ui: React.ReactElement) {
  const container = document.createElement("div");
  const root = createRoot(container);
  document.body.appendChild(container);
  containers.push(container);
  roots.push(root);

  act(() => {
    root.render(ui);
  });

  return container;
}

afterEach(() => {
  for (const root of roots) {
    act(() => {
      root.unmount();
    });
  }
  for (const container of containers) {
    container.remove();
  }
  roots = [];
  containers = [];
});

describe("HoldingForm", () => {
  it("uses KRW as the avg cost label when the selected ticker is Korean", () => {
    const container = render(<HoldingForm />);

    expect(container.textContent).toContain("Avg cost (USD)");
    expect(container.querySelector<HTMLInputElement>("#avg")?.placeholder).toBe(
      "185.50",
    );

    const koreanTickerButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Select Korean ticker",
    );
    expect(koreanTickerButton).toBeTruthy();

    act(() => {
      koreanTickerButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("Avg cost (KRW)");
    expect(container.querySelector<HTMLInputElement>("#avg")?.placeholder).toBe(
      "75000",
    );
  });
});
