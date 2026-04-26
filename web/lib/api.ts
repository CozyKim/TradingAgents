/**
 * Thin fetch wrapper that always sends cookies and parses JSON.
 * Throws an Error with the API's `detail` message on non-2xx.
 *
 * When the body is FormData the Content-Type header is omitted so the
 * browser can set the correct multipart boundary.
 */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  const baseHeaders: Record<string, string> = {
    "X-Requested-With": "fetch",
  };
  if (!isFormData) {
    baseHeaders["Content-Type"] = "application/json";
  }
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      ...baseHeaders,
      ...(init.headers as Record<string, string> | undefined),
    },
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail ?? response.statusText;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}
