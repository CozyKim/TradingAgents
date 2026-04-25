export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="h-2 w-2 rounded-full bg-accent" aria-hidden />
      {!collapsed && <span className="text-sm font-bold text-text-1">TradingAgents</span>}
    </div>
  );
}
