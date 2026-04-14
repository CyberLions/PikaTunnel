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
  if (error) return <div className="text-red-400">{error}</div>;
  if (!data) return null;

  const cards = [
    {
      title: "HTTP Routes",
      value: data.routeCount,
      sub: `${data.routeEnabled} enabled`,
      color: "text-blue-400",
    },
    {
      title: "Stream Routes",
      value: data.streamCount,
      sub: `${data.streamEnabled} enabled`,
      color: "text-purple-400",
    },
    {
      title: "VPN Configs",
      value: data.vpnCount,
      sub: data.health?.vpn.status || "unknown",
      color: "text-green-400",
    },
    {
      title: "Nginx",
      value: data.health?.nginx.running ? "Running" : "Stopped",
      sub: data.health?.nginx.config_valid ? "Config valid" : "Config invalid",
      color: data.health?.nginx.running ? "text-green-400" : "text-red-400",
    },
  ];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-slate-100">Dashboard</h1>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div key={card.title} className="card">
            <p className="text-sm font-medium text-slate-400">{card.title}</p>
            <p className={`mt-2 text-3xl font-bold ${card.color}`}>{card.value}</p>
            <p className="mt-1 text-sm text-slate-500">{card.sub}</p>
          </div>
        ))}
      </div>

      {data.health && (
        <div className="card mt-8">
          <h2 className="mb-4 text-lg font-semibold text-slate-200">System Status</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Database</span>
              <StatusBadge status={data.health.database ? "connected" : "error"} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Nginx</span>
              <StatusBadge status={data.health.nginx.running ? "running" : "stopped"} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">VPN</span>
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
