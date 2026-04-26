"use client";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

type Props = {
  selected: string[];
  onClear: () => void;
};

export function CompareToolbar({ selected, onClear }: Props) {
  const router = useRouter();
  const ready = selected.length === 2;
  return (
    <div className="flex items-center justify-between gap-2 mb-2 text-xs text-text-3">
      <span>
        {selected.length} / 2 selected
        {selected.length > 0 && (
          <button
            className="ml-2 underline"
            type="button"
            onClick={onClear}
          >
            clear
          </button>
        )}
      </span>
      <Button
        variant={ready ? "default" : "outline"}
        size="sm"
        disabled={!ready}
        onClick={() =>
          router.push(`/history/compare?ids=${selected[0]},${selected[1]}`)
        }
      >
        Compare
      </Button>
    </div>
  );
}
