import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-12 w-full rounded-xl bg-bg-2 px-4 text-[15px] text-text-1 placeholder:text-text-3",
      "ring-1 ring-inset ring-transparent transition-[box-shadow,background-color]",
      "focus-visible:bg-bg-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
      "disabled:opacity-40",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
