import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const fetchCache = "force-no-store";
export const revalidate = 0;

function resolveBackendBase(): string {
  const base = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
  return base || "http://localhost:8000";
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  const backend = resolveBackendBase();
  const url = `${backend}/api/runs/${encodeURIComponent(params.id)}/stream`;

  const upstreamHeaders: Record<string, string> = {
    accept: "text/event-stream",
  };
  const cookie = request.headers.get("cookie");
  if (cookie) upstreamHeaders.cookie = cookie;
  const lastEventId = request.headers.get("last-event-id");
  if (lastEventId) upstreamHeaders["last-event-id"] = lastEventId;

  const upstream = await fetch(url, {
    method: "GET",
    headers: upstreamHeaders,
    cache: "no-store",
    redirect: "manual",
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "");
    return new Response(text || null, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "text/plain; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  }

  // Pump upstream chunks via `start` (not `pull`) so chunks are forwarded
  // immediately as they arrive — independent of the consumer's backpressure
  // signals. This is critical for SSE where the response is long-lived.
  const upstreamReader = upstream.body.getReader();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      (async () => {
        try {
          for (;;) {
            const { done, value } = await upstreamReader.read();
            if (done) {
              controller.close();
              return;
            }
            if (value) controller.enqueue(value);
          }
        } catch (err) {
          try {
            controller.error(err);
          } catch {
            // controller may already be closed
          }
        }
      })();
    },
    cancel(reason) {
      upstreamReader.cancel(reason).catch(() => {});
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-store, no-transform",
      "x-accel-buffering": "no",
      connection: "keep-alive",
    },
  });
}
