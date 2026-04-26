interface StreamLocation {
  protocol: string;
  hostname: string;
}

interface ResolveRunStreamUrlOptions {
  apiBaseUrl?: string;
  browserApiBaseUrl?: string;
  location?: StreamLocation;
}

const DEFAULT_API_PORT = "8000";

function trimTrailingSlash(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return trimmed.replace(/\/+$/, "");
}

function getBrowserLocation(): StreamLocation | undefined {
  if (typeof window === "undefined") return undefined;
  return {
    protocol: window.location.protocol,
    hostname: window.location.hostname,
  };
}

function isLocalHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function isDockerInternalHost(baseUrl: string): boolean {
  try {
    const parsed = new URL(baseUrl);
    return parsed.hostname === "api";
  } catch {
    return false;
  }
}

function isLikelyBrowserReachable(baseUrl: string): boolean {
  try {
    const parsed = new URL(baseUrl);
    return parsed.hostname !== "api";
  } catch {
    return false;
  }
}

function dockerHostBaseUrl(baseUrl: string, location: StreamLocation): string | undefined {
  try {
    const parsed = new URL(baseUrl);
    const port = parsed.port || DEFAULT_API_PORT;
    return `${location.protocol}//${location.hostname}:${port}`;
  } catch {
    return undefined;
  }
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

  const configuredBase = trimTrailingSlash(
    options.apiBaseUrl ?? process.env.NEXT_PUBLIC_API_URL,
  );
  const location = options.location ?? getBrowserLocation();

  if (configuredBase && isDockerInternalHost(configuredBase) && location) {
    const browserBase = dockerHostBaseUrl(configuredBase, location);
    if (browserBase) return `${browserBase}${path}`;
  }

  if (configuredBase && isLikelyBrowserReachable(configuredBase)) {
    return `${configuredBase}${path}`;
  }

  if (location && isLocalHost(location.hostname)) {
    return `${location.protocol}//${location.hostname}:${DEFAULT_API_PORT}${path}`;
  }

  return path;
}
