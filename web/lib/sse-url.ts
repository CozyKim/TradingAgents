interface ResolveRunStreamUrlOptions {
  browserApiBaseUrl?: string;
}

function trimTrailingSlash(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return trimmed.replace(/\/+$/, "");
}

export function resolveRunStreamUrl(
  runId: string,
  options: ResolveRunStreamUrlOptions = {},
): string {
  const path = `/api/runs/${encodeURIComponent(runId)}/stream`;
  const explicitBrowserBase = trimTrailingSlash(
    options.browserApiBaseUrl ?? process.env.NEXT_PUBLIC_BROWSER_API_URL,
  );
  if (explicitBrowserBase) return `${explicitBrowserBase}${path}`;
  return path;
}
