/**
 * Thin fetch wrapper that always sends cookies and parses JSON.
 * Throws an Error with the API's `detail` message on non-2xx.
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
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "fetch",
      ...init.headers,
    },
    ...init,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail ?? response.statusText;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}
