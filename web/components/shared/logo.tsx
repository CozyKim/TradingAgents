export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-2">
      <span
        aria-hidden
        className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-[13px] font-black text-white shadow-card"
        style={{ letterSpacing: "-0.05em" }}
      >
        T
      </span>
      {!collapsed && (
        <span className="text-[15px] font-bold tracking-[-0.025em] text-text-1">
          TradingAgents
        </span>
      )}
    </div>
  );
}
