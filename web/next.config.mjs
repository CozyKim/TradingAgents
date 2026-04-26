/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const destination =
      process.env.NEXT_PUBLIC_API_URL
        ? `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`
        : "http://localhost:8000/api/:path*";
    // `fallback` runs AFTER file-system + dynamic routes, so our Route Handler
    // at app/api/runs/[id]/stream/route.ts wins for SSE; everything else
    // still proxies to the backend transparently.
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination,
        },
      ],
    };
  },
};
export default nextConfig;
