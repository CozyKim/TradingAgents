import "./globals.css";

import type { Metadata, Viewport } from "next";

import { ServiceWorkerRegistrar } from "@/components/shared/service-worker-registrar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "TradingAgents",
  description: "Personal trading analysis workbench",
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/icons/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
    shortcut: [{ url: "/icons/icon-32.png", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#FFFFFF",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-bg-0 text-text-1 antialiased">
        <ServiceWorkerRegistrar />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
