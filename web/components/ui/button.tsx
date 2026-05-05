import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-xl text-[15px] font-bold tracking-[-0.01em] transition-[transform,background-color,color] duration-100 active:scale-[0.985] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        default: "bg-accent text-white hover:bg-[#1B64DA]",
        secondary:
          "bg-accent-muted text-accent hover:bg-[#D6E7FD]",
        outline:
          "bg-bg-1 text-text-1 ring-1 ring-inset ring-border-1 hover:bg-bg-2",
        ghost: "text-text-2 hover:bg-bg-2 hover:text-text-1",
        destructive:
          "bg-signal-buy/10 text-signal-buy hover:bg-signal-buy/15",
      },
      size: {
        default: "h-12 px-5",
        sm: "h-9 px-4 text-[13px] rounded-lg",
        lg: "h-14 px-6 text-[16px] rounded-2xl",
        icon: "h-10 w-10 rounded-xl",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";
