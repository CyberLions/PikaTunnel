import { useEffect, useState } from "react";
import { get } from "../api/client";
import { listRoutes } from "../api/routes";
import { listStreams } from "../api/streams";
import { listVPNs } from "../api/vpn";
import type { HealthStatus } from "../types";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

interface DashboardData {
  health: HealthStatus | null;
  routeCount: number;
  routeEnabled: number;
  streamCount: number;
  streamEnabled: number;
  vpnCount: number;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [health, routes, streams, vpns] = await Promise.all([
          get<HealthStatus>("/health").catch(() => null),
          listRoutes().catch(() => ({ items: [], total: 0, page: 1, per_page: 50 })),
          listStreams().catch(() => ({ items: [], total: 0, page: 1, per_page: 50 })),
          listVPNs().catch(() => []),
        ]);
        setData({
          health,
          routeCount: routes.total,
          routeEnabled: routes.items.filter((r) => r.enabled).length,
          streamCount: streams.total,
          streamEnabled: streams.items.filter((s) => s.enabled).length,
          vpnCount: vpns.length,
        });
      } catch {
        setError("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="card text-red-400">{error}</div>;
  if (!data) return null;

  const cards = [
    {
      title: "HTTP Routes",
      value: data.routeCount,
      sub: `${data.routeEnabled} active`,
      gradient: "from-orange-500/20 to-orange-600/5",
      accent: "text-orange-400",
      border: "border-orange-500/15",
    },
    {
      title: "Stream Routes",
      value: data.streamCount,
      sub: `${data.streamEnabled} active`,
      gradient: "from-purple-500/20 to-purple-600/5",
      accent: "text-purple-400",
      border: "border-purple-500/15",
    },
    {
      title: "VPN Configs",
      value: data.vpnCount,
      sub: data.health?.vpn.status || "unknown",
      gradient: "from-emerald-500/20 to-emerald-600/5",
      accent: "text-emerald-400",
      border: "border-emerald-500/15",
    },
    {
      title: "Nginx",
      value: data.health?.nginx.running ? "Running" : "Stopped",
      sub: data.health?.nginx.config_valid ? "Config valid" : "Config invalid",
      gradient: data.health?.nginx.running ? "from-emerald-500/20 to-emerald-600/5" : "from-red-500/20 to-red-600/5",
      accent: data.health?.nginx.running ? "text-emerald-400" : "text-red-400",
      border: data.health?.nginx.running ? "border-emerald-500/15" : "border-red-500/15",
    },
  ];

  return (
    <div>
      <div className="mb-8 flex items-center gap-4">
        <img src="/logo.png" alt="" className="h-10 w-10 rounded-xl" />
        <div>
          <h1 className="text-2xl font-bold text-stone-100">Dashboard</h1>
          <p className="text-sm text-stone-500">Your tunnels at a glance</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div key={card.title} className={`rounded-2xl border ${card.border} bg-gradient-to-br ${card.gradient} p-5 transition-all duration-200 hover:scale-[1.02]`}>
            <p className="text-xs font-semibold uppercase tracking-wider text-stone-500">{card.title}</p>
            <p className={`mt-2 text-3xl font-bold ${card.accent}`}>{card.value}</p>
            <p className="mt-1 text-sm text-stone-500">{card.sub}</p>
          </div>
        ))}
      </div>

      {data.health && (
        <div className="card mt-8">
          <h2 className="mb-5 text-lg font-bold text-stone-100">System Status</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-xl bg-neutral-950/50 px-4 py-3">
              <span className="text-sm font-medium text-stone-300">Database</span>
              <StatusBadge status={data.health.database ? "connected" : "error"} />
            </div>
            <div className="flex items-center justify-between rounded-xl bg-neutral-950/50 px-4 py-3">
              <span className="text-sm font-medium text-stone-300">Nginx</span>
              <StatusBadge status={data.health.nginx.running ? "running" : "stopped"} />
            </div>
            <div className="flex items-center justify-between rounded-xl bg-neutral-950/50 px-4 py-3">
              <span className="text-sm font-medium text-stone-300">VPN</span>
              <StatusBadge
                status={
                  data.health.vpn.status === "connected"
                    ? "connected"
                    : data.health.vpn.status === "connecting"
                      ? "connecting"
                      : "disconnected"
                }
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
