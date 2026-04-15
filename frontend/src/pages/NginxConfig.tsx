import { useEffect, useState, useCallback } from "react";
import { getNginxStatus, reloadNginx, previewConfig } from "../api/nginx";
import type { NginxStatus } from "../types";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import ConfirmDialog from "../components/ConfirmDialog";
import Toast from "../components/Toast";

export default function NginxConfig() {
  const [status, setStatus] = useState<NginxStatus | null>(null);
  const [httpConfig, setHttpConfig] = useState<string>("");
  const [streamConfig, setStreamConfig] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "info" | "success" | "error" } | null>(null);
  const [confirmReload, setConfirmReload] = useState(false);

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

  const clearToast = useCallback(() => setToast(null), []);

  async function handleReload() {
    setConfirmReload(false);
    setReloading(true);
    setToast(null);
    try {
      const res = await reloadNginx();
      setToast({ message: res.message || "Nginx reloaded successfully", type: "success" });
      await load();
    } catch {
      setToast({ message: "Failed to reload nginx", type: "error" });
    } finally {
      setReloading(false);
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">Nginx Configuration</h1>
          <p className="text-sm text-stone-500 mt-1">Preview and manage your nginx config</p>
        </div>
        <button onClick={() => setConfirmReload(true)} disabled={reloading} className="btn-primary">
          {reloading ? "Reloading..." : "Reload Nginx"}
        </button>
      </div>

      <ConfirmDialog
        open={confirmReload}
        title="Reload Nginx"
        message="This will reload the nginx configuration. Active connections may be briefly interrupted."
        confirmLabel="Reload"
        onConfirm={handleReload}
        onCancel={() => setConfirmReload(false)}
      />

      {toast && <Toast message={toast.message} type={toast.type} onClose={clearToast} />}

      {status && (
        <div className="card mb-6">
          <h2 className="mb-4 text-lg font-bold text-stone-100">Status</h2>
          <div className="flex gap-8">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-stone-400">Process</span>
              <StatusBadge status={status.running ? "running" : "stopped"} />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-stone-400">Config</span>
              <StatusBadge status={status.config_valid ? "enabled" : "error"} />
            </div>
          </div>
        </div>
      )}

      <div className="card mb-6">
        <h2 className="mb-4 text-lg font-bold text-stone-100">HTTP Configuration</h2>
        <pre className="code-block max-h-[600px] overflow-y-auto">
          {httpConfig || "No HTTP config generated yet."}
        </pre>
      </div>

      {streamConfig && (
        <div className="card">
          <h2 className="mb-4 text-lg font-bold text-stone-100">Stream Configuration</h2>
          <pre className="code-block max-h-[600px] overflow-y-auto">
            {streamConfig}
          </pre>
        </div>
      )}
    </div>
  );
}
