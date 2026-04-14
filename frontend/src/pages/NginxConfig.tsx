import { useEffect, useState } from "react";
import { getNginxStatus, reloadNginx, previewConfig } from "../api/nginx";
import type { NginxStatus } from "../types";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

export default function NginxConfig() {
  const [status, setStatus] = useState<NginxStatus | null>(null);
  const [httpConfig, setHttpConfig] = useState<string>("");
  const [streamConfig, setStreamConfig] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    try {
      const [s, c] = await Promise.all([
        getNginxStatus().catch(() => null),
        previewConfig().catch(() => ({ http_config: "Failed to load", stream_config: "" })),
      ]);
      setStatus(s);
      setHttpConfig(c.http_config);
      setStreamConfig(c.stream_config);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleReload() {
    if (!confirm("Reload nginx configuration?")) return;
    setReloading(true);
    setMessage(null);
    try {
      const res = await reloadNginx();
      setMessage(res.message || "Nginx reloaded successfully");
      await load();
    } catch {
      setMessage("Failed to reload nginx");
    } finally {
      setReloading(false);
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Nginx Configuration</h1>
        <button onClick={handleReload} disabled={reloading} className="btn-primary">
          {reloading ? "Reloading..." : "Reload Nginx"}
        </button>
      </div>

      {message && (
        <div className="mb-4 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-400">
          {message}
        </div>
      )}

      {status && (
        <div className="card mb-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-200">Status</h2>
          <div className="flex gap-8">
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-400">Process</span>
              <StatusBadge status={status.running ? "running" : "stopped"} />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-400">Config</span>
              <StatusBadge status={status.config_valid ? "enabled" : "error"} />
            </div>
          </div>
        </div>
      )}

      <div className="card mb-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-200">HTTP Configuration</h2>
        <pre className="code-block max-h-[600px] overflow-y-auto">
          {httpConfig || "No HTTP config generated yet."}
        </pre>
      </div>

      {streamConfig && (
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-slate-200">Stream Configuration</h2>
          <pre className="code-block max-h-[600px] overflow-y-auto">
            {streamConfig}
          </pre>
        </div>
      )}
    </div>
  );
}
