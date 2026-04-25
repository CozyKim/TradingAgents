import "./globals.css";

import type { Metadata } from "next";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "TradingAgents",
  description: "Personal trading analysis workbench",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="bg-bg-0 text-text-1 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
