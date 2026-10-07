"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export type ServiceCheck = {
  name: string;
  status: "up" | "down" | "unknown";
  latency_ms?: number | null;
  required_for_ready: boolean;
  detail?: string | null;
};

export type ReadinessPayload = {
  status: "ready" | "not_ready";
  ready: boolean;
  service: string;
  version: string;
  environment: string;
  phase: string;
  checks: ServiceCheck[];
  time: string;
};

async function fetchReadiness(): Promise<ReadinessPayload> {
  const res = await fetch(`${API_BASE}/health/ready`, { cache: "no-store" });
  if (!res.ok && res.status !== 503) {
    throw new Error(`API responded ${res.status}`);
  }
  const body = (await res.json()) as ReadinessPayload;
  if (!body || typeof body.ready !== "boolean") {
    throw new Error("Invalid readiness payload");
  }
  return body;
}

const CARD_LABEL_KEYS: Record<string, string> = {
  api: "apiConnectivity",
  postgres: "databaseConnectivity",
  valkey: "valkeyConnectivity",
  worker: "workerStatus",
  scheduler: "schedulerStatus",
};

const CARD_ORDER = ["api", "postgres", "valkey", "worker", "scheduler"] as const;

function statusVariant(status: ServiceCheck["status"] | "unreachable") {
  if (status === "up") return "success" as const;
  if (status === "down" || status === "unreachable") return "destructive" as const;
  return "warning" as const;
}

export function StatusBoard({ webVersion }: { webVersion: string }) {
  const t = useTranslations("Shell");
  const { data, error, isFetching, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["health", "ready"],
    queryFn: fetchReadiness,
    refetchInterval: 10_000,
  });

  const checks: ServiceCheck[] = data?.checks ?? [];
  const checkByName = (name: string): ServiceCheck | undefined =>
    checks.find((c) => c.name === name);

  const cards = CARD_ORDER.map((name) => {
    if (error && name === "api") {
      return {
        name,
        status: "unreachable" as const,
        detail: error instanceof Error ? error.message : "unreachable",
      };
    }
    if (error) {
      return { name, status: "unknown" as const, detail: "—" };
    }
    const check = checkByName(name);
    return {
      name,
      status: (check?.status ?? "unknown") as ServiceCheck["status"],
      detail: check?.detail ?? "—",
    };
  });

  const readyState = data ? (data.ready ? "systemReady" : "notReady") : "waiting";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={data?.ready ? "success" : "destructive"}>{t(readyState)}</Badge>
          <Badge variant="outline">{t("environment", { value: data?.environment ?? "UNKNOWN" })}</Badge>
          <Badge variant="outline">{t("phase", { value: data?.phase ?? "V1A-0" })}</Badge>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? t("refreshing") : t("refresh")}
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.name}>
            <CardHeader>
              <CardTitle>{t(CARD_LABEL_KEYS[card.name])}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              <Badge variant={statusVariant(card.status)}>
                {card.status === "unreachable" ? t("unreachable") : card.status.toUpperCase()}
              </Badge>
              <p className="text-xs text-zinc-500">{card.detail || "—"}</p>
            </CardContent>
          </Card>
        ))}

        <Card>
          <CardHeader>
            <CardTitle>{t("buildInfo")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-zinc-400">
            <p>{t("apiVersion", { value: data?.version ?? "UNKNOWN" })}</p>
            <p>{t("webVersion", { value: webVersion })}</p>
            <p>{t("phase", { value: data?.phase ?? "V1A-0" })}</p>
            <p>
              {t("lastUpdated", {
                value: dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : "never",
              })}
            </p>
          </CardContent>
        </Card>
      </div>

      <p className="text-xs text-zinc-600">{t("bootstrapNote")}</p>
    </div>
  );
}
