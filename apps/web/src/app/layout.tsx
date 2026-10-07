import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";

import { Providers } from "@/components/providers";
import messages from "../../messages/en.json";
import "./globals.css";

export const metadata: Metadata = {
  title: "RevenueOS",
  description: "RevenueOS / AffiliateOS — V1A-0 bootstrap shell",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <NextIntlClientProvider locale="en" messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
