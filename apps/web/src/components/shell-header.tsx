"use client";

import { useTranslations } from "next-intl";

export function ShellHeader({ webVersion }: { webVersion: string }) {
  const t = useTranslations("Shell");

  return (
    <header className="mb-8 border-b border-zinc-800 pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="mt-1 text-sm text-zinc-400">{t("subtitle")}</p>
        </div>
        <span className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-400">
          v{webVersion}
        </span>
      </div>
    </header>
  );
}
