import "./globals.css";

import type { Metadata, Viewport } from "next";

import { ServiceWorkerRegistrar } from "@/components/shared/service-worker-registrar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "TradingAgents",
  description: "Personal trading analysis workbench",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0a0a0b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="bg-bg-0 text-text-1 antialiased">
        <ServiceWorkerRegistrar />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
