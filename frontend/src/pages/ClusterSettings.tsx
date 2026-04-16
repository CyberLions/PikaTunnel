import { useEffect, useState, useCallback } from "react";
import { getClusterSettings, updateClusterSettings, testClusterConnection, clearCredentials, type ClusterSettings } from "../api/cluster";
import LoadingSpinner from "../components/LoadingSpinner";
import Toast from "../components/Toast";
import ConfirmDialog from "../components/ConfirmDialog";

export default function ClusterSettingsPage() {
  const [settings, setSettings] = useState<ClusterSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "info" | "success" | "error" } | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  // Form state for sensitive fields (not in GET response)
  const [tokenInput, setTokenInput] = useState("");
  const [caCertInput, setCaCertInput] = useState("");

  const clearToast = useCallback(() => setToast(null), []);

  async function load() {
    try {
      const s = await getClusterSettings();
      setSettings(s);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        k8s_api_url: settings.k8s_api_url,
        k8s_namespace: settings.k8s_namespace,
        k8s_in_cluster: settings.k8s_in_cluster,
        default_ingress_class: settings.default_ingress_class,
        default_cluster_issuer: settings.default_cluster_issuer,
        default_cloudflare_proxied: settings.default_cloudflare_proxied,
        backend_service_name: settings.backend_service_name,
        backend_service_port: settings.backend_service_port,
        k8s_loadbalancer_service_name: settings.k8s_loadbalancer_service_name,
        authentik_outpost_url: settings.authentik_outpost_url,
        authentik_signin_url: settings.authentik_signin_url,
        authentik_response_headers: settings.authentik_response_headers,
        authentik_auth_snippet: settings.authentik_auth_snippet,
      };
      if (tokenInput) payload.k8s_token = tokenInput;
      if (caCertInput) payload.k8s_ca_cert = caCertInput;

      const updated = await updateClusterSettings(payload);
      setSettings(updated);
      setTokenInput("");
      setCaCertInput("");
      setToast({ message: "Settings saved", type: "success" });
    } catch {
      setToast({ message: "Failed to save settings", type: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    try {
      const result = await testClusterConnection();
      if (result.connected) {
        setToast({ message: `Connected to cluster${result.version ? ` (${result.version})` : ""}`, type: "success" });
      } else {
        setToast({ message: result.error || "Connection failed", type: "error" });
      }
    } catch {
      setToast({ message: "Connection test failed", type: "error" });
    } finally {
      setTesting(false);
    }
  }

  async function handleClearCreds() {
    setConfirmClear(false);
    await clearCredentials();
    await load();
    setToast({ message: "Credentials cleared", type: "info" });
  }

  if (loading) return <LoadingSpinner />;
  if (!settings) return null;

  const set = (updates: Partial<ClusterSettings>) => setSettings({ ...settings, ...updates });

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-stone-100">Cluster Settings</h1>
        <p className="text-sm text-stone-500 mt-1">Configure Kubernetes connection and ingress defaults</p>
      </div>

      {/* Kubernetes Connection */}
      <div className="card mb-6">
        <h2 className="text-lg font-bold text-stone-100 mb-4">Kubernetes Connection</h2>
        <div className="space-y-4">
          <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
            <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={settings.k8s_in_cluster} onChange={(e) => set({ k8s_in_cluster: e.target.checked })} />
            Use in-cluster config
          </label>
          {!settings.k8s_in_cluster && (
            <>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">API Server URL</label>
                <input className="input-field" placeholder="https://kubernetes.default.svc" value={settings.k8s_api_url || ""} onChange={(e) => set({ k8s_api_url: e.target.value || null })} />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">
                  Service Account Token {settings.has_token && <span className="text-emerald-400 text-xs ml-2">configured</span>}
                </label>
                <input type="password" className="input-field" placeholder={settings.has_token ? "Leave blank to keep current" : "Paste service account token"} value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">
                  CA Certificate {settings.has_ca_cert && <span className="text-emerald-400 text-xs ml-2">configured</span>}
                </label>
                <textarea rows={3} className="input-field font-mono text-xs" placeholder={settings.has_ca_cert ? "Leave blank to keep current" : "Paste CA certificate PEM"} value={caCertInput} onChange={(e) => setCaCertInput(e.target.value)} />
              </div>
            </>
          )}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Namespace</label>
            <input className="input-field" value={settings.k8s_namespace} onChange={(e) => set({ k8s_namespace: e.target.value })} />
          </div>
          <div className="flex gap-3">
            <button onClick={handleTest} disabled={testing} className="btn-secondary text-sm">
              {testing ? "Testing..." : "Test Connection"}
            </button>
            {(settings.has_token || settings.has_ca_cert) && (
              <button onClick={() => setConfirmClear(true)} className="text-sm text-red-400 hover:text-red-300 transition-colors">
                Clear Credentials
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Backend Service */}
      <div className="card mb-6">
        <h2 className="text-lg font-bold text-stone-100 mb-4">Backend Service</h2>
        <p className="text-xs text-stone-500 mb-3">The Kubernetes service that ingresses should route to</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Service Name</label>
            <input className="input-field" value={settings.backend_service_name} onChange={(e) => set({ backend_service_name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Service Port</label>
            <input type="number" className="input-field" value={settings.backend_service_port} onChange={(e) => set({ backend_service_port: parseInt(e.target.value) || 80 })} />
          </div>
        </div>
        <div className="mt-4">
          <label className="mb-1.5 block text-sm font-medium text-stone-300">LoadBalancer Service Name</label>
          <input
            className="input-field"
            placeholder="e.g. pikatunnel (leave empty to disable port sync)"
            value={settings.k8s_loadbalancer_service_name || ""}
            onChange={(e) => set({ k8s_loadbalancer_service_name: e.target.value || null })}
          />
          <p className="mt-1 text-xs text-stone-600">
            The Service whose <code>spec.ports</code> pikatunnel patches when you add or toggle stream routes. Required for "Sync Service Ports" to work.
          </p>
        </div>
      </div>

      {/* Ingress Defaults */}
      <div className="card mb-6">
        <h2 className="text-lg font-bold text-stone-100 mb-4">Ingress Defaults</h2>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Ingress Class</label>
            <input className="input-field" value={settings.default_ingress_class} onChange={(e) => set({ default_ingress_class: e.target.value })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Cert-Manager Cluster Issuer</label>
            <input className="input-field" value={settings.default_cluster_issuer} onChange={(e) => set({ default_cluster_issuer: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
            <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={settings.default_cloudflare_proxied} onChange={(e) => set({ default_cloudflare_proxied: e.target.checked })} />
            Cloudflare Proxy (default)
          </label>
        </div>
      </div>

      {/* Authentik */}
      <div className="card mb-6">
        <h2 className="text-lg font-bold text-stone-100 mb-4">Authentik Configuration</h2>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Outpost URL (auth-url)</label>
            <input className="input-field" placeholder="http://ak-outpost-....svc.cluster.local:9000/outpost.goauthentik.io/auth/nginx" value={settings.authentik_outpost_url || ""} onChange={(e) => set({ authentik_outpost_url: e.target.value || null })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Sign-in URL Template (auth-signin)</label>
            <input className="input-field" placeholder="https://{host}/outpost.goauthentik.io/start?rd=$scheme://$http_host$escaped_request_uri" value={settings.authentik_signin_url || ""} onChange={(e) => set({ authentik_signin_url: e.target.value || null })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Response Headers</label>
            <input className="input-field text-xs" value={settings.authentik_response_headers} onChange={(e) => set({ authentik_response_headers: e.target.value })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Auth Snippet</label>
            <textarea rows={2} className="input-field font-mono text-xs" placeholder='proxy_set_header X-Forwarded-Host $http_host;' value={settings.authentik_auth_snippet || ""} onChange={(e) => set({ authentik_auth_snippet: e.target.value || null })} />
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end gap-3">
        <button onClick={handleSave} disabled={saving} className="btn-primary">
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>

      <ConfirmDialog
        open={confirmClear}
        title="Clear Credentials"
        message="This will remove the stored service account token and CA certificate. You'll need to re-enter them to connect."
        confirmLabel="Clear"
        danger
        onConfirm={handleClearCreds}
        onCancel={() => setConfirmClear(false)}
      />

      {toast && <Toast message={toast.message} type={toast.type} onClose={clearToast} />}
    </div>
  );
}
