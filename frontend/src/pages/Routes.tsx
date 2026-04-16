import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  listRoutes, createRoute, updateRoute, deleteRoute, syncIngress,
  exportRoutesCsv, importRoutesCsv,
  type ImportResult,
} from "../api/routes";
import { reloadNginx } from "../api/nginx";
import { syncAllIngresses } from "../api/cluster";
import type { ProxyRoute } from "../types";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";
import ConfirmDialog from "../components/ConfirmDialog";

type FormData = {
  name: string;
  host: string;
  path: string;
  destination: string;
  port: string;
  ssl_enabled: boolean;
  ssl_cert_name: string;
  ssl_cert_path: string;
  ssl_key_path: string;
  enabled: boolean;
  groups: string;
  k8s_ingress_enabled: boolean;
  k8s_cloudflare_proxied: string;
  k8s_cert_manager_enabled: boolean;
  k8s_cluster_issuer: string;
  k8s_authentik_enabled: boolean;
  k8s_proxy_body_size: string;
  k8s_proxy_read_timeout: string;
  k8s_proxy_send_timeout: string;
  k8s_proxy_connect_timeout: string;
};

const emptyForm: FormData = {
  name: "",
  host: "",
  path: "/",
  destination: "",
  port: "80",
  ssl_enabled: false,
  ssl_cert_name: "",
  ssl_cert_path: "",
  ssl_key_path: "",
  enabled: true,
  groups: "",
  k8s_ingress_enabled: false,
  k8s_cloudflare_proxied: "default",
  k8s_cert_manager_enabled: false,
  k8s_cluster_issuer: "",
  k8s_authentik_enabled: false,
  k8s_proxy_body_size: "",
  k8s_proxy_read_timeout: "",
  k8s_proxy_send_timeout: "",
  k8s_proxy_connect_timeout: "",
};

export default function Routes() {
  const [routes, setRoutes] = useState<ProxyRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ProxyRoute | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [syncingRowId, setSyncingRowId] = useState<string | null>(null);

  async function handleSyncAll() {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await syncAllIngresses();
      const hasErrors = res.errors > 0;
      setSyncMsg({
        kind: hasErrors ? "err" : "ok",
        text: `Synced ${res.synced} of ${res.total} ingresses${hasErrors ? ` (${res.errors} failed)` : ""}`,
      });
    } catch (e) {
      setSyncMsg({ kind: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setSyncing(false);
    }
  }

  async function handleRowSync(id: string, name: string) {
    setSyncingRowId(id);
    setSyncMsg(null);
    try {
      const res = await syncIngress(id);
      setSyncMsg({ kind: "ok", text: res.message || `Synced ${name}` });
    } catch (e) {
      setSyncMsg({ kind: "err", text: `Sync failed for ${name}: ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setSyncingRowId(null);
    }
  }

  async function handleExport() {
    try {
      await exportRoutesCsv();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const result = await importRoutesCsv(text);
      setImportResult(result);
      await reloadNginx().catch(() => {});
      await load();
    } catch (err) {
      setImportResult({
        created: 0,
        updated: 0,
        skipped: 0,
        errors: [err instanceof Error ? err.message : String(err)],
      });
    } finally {
      setImporting(false);
    }
  }

  async function load() {
    try {
      const res = await listRoutes();
      setRoutes(res.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setModalOpen(true);
  }

  function openEdit(route: ProxyRoute) {
    setEditing(route);
    setForm({
      name: route.name,
      host: route.host,
      path: route.path,
      destination: route.destination,
      port: String(route.port),
      ssl_enabled: route.ssl_enabled,
      ssl_cert_name: route.ssl_cert_name || "",
      ssl_cert_path: route.ssl_cert_path || "",
      ssl_key_path: route.ssl_key_path || "",
      enabled: route.enabled,
      groups: route.groups || "",
      k8s_ingress_enabled: route.k8s_ingress_enabled,
      k8s_cloudflare_proxied: route.k8s_cloudflare_proxied === null ? "default" : route.k8s_cloudflare_proxied ? "on" : "off",
      k8s_cert_manager_enabled: route.k8s_cert_manager_enabled,
      k8s_cluster_issuer: route.k8s_cluster_issuer || "",
      k8s_authentik_enabled: route.k8s_authentik_enabled,
      k8s_proxy_body_size: route.k8s_proxy_body_size || "",
      k8s_proxy_read_timeout: route.k8s_proxy_read_timeout || "",
      k8s_proxy_send_timeout: route.k8s_proxy_send_timeout || "",
      k8s_proxy_connect_timeout: route.k8s_proxy_connect_timeout || "",
    });
    setModalOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        host: form.host,
        path: form.path,
        destination: form.destination,
        port: parseInt(form.port),
        ssl_enabled: form.ssl_enabled || !!form.ssl_cert_name,
        ssl_cert_name: form.ssl_cert_name || null,
        ssl_cert_path: form.ssl_cert_path || null,
        ssl_key_path: form.ssl_key_path || null,
        enabled: form.enabled,
        groups: form.groups,
        k8s_ingress_enabled: form.k8s_ingress_enabled,
        k8s_cloudflare_proxied: form.k8s_cloudflare_proxied === "default" ? null : form.k8s_cloudflare_proxied === "on",
        k8s_cert_manager_enabled: form.k8s_cert_manager_enabled,
        k8s_cluster_issuer: form.k8s_cluster_issuer || null,
        k8s_authentik_enabled: form.k8s_authentik_enabled,
        k8s_proxy_body_size: form.k8s_proxy_body_size || null,
        k8s_proxy_read_timeout: form.k8s_proxy_read_timeout || null,
        k8s_proxy_send_timeout: form.k8s_proxy_send_timeout || null,
        k8s_proxy_connect_timeout: form.k8s_proxy_connect_timeout || null,
        k8s_custom_annotations: null,
      };
      if (editing) {
        await updateRoute(editing.id, payload);
      } else {
        await createRoute(payload);
      }
      await reloadNginx().catch(() => {});
      setModalOpen(false);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    await deleteRoute(id);
    await reloadNginx().catch(() => {});
    setConfirmDelete(null);
    await load();
  }

  async function handleToggle(route: ProxyRoute) {
    await updateRoute(route.id, { enabled: !route.enabled });
    await reloadNginx().catch(() => {});
    await load();
  }

  const columns = [
    { key: "name", header: "Name", render: (r: ProxyRoute) => <span className="font-semibold text-stone-100">{r.name}</span> },
    { key: "host", header: "Host", render: (r: ProxyRoute) => <span className="text-stone-300">{r.host}</span> },
    { key: "path", header: "Path", render: (r: ProxyRoute) => <code className="text-xs text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded-md">{r.path}</code> },
    { key: "dest", header: "Destination", render: (r: ProxyRoute) => <span className="font-mono text-xs text-stone-400">{r.destination}:{r.port}</span> },
    { key: "ssl", header: "SSL", render: (r: ProxyRoute) => r.ssl_enabled ? <span className="text-emerald-400 text-xs font-semibold">Yes</span> : <span className="text-stone-600 text-xs">No</span> },
    { key: "groups", header: "Groups", render: (r: ProxyRoute) => r.groups ? <span className="text-xs text-orange-400">{r.groups}</span> : <span className="text-xs text-stone-600">all</span> },
    { key: "k8s", header: "K8s", render: (r: ProxyRoute) => r.k8s_ingress_enabled ? <span className="text-xs font-semibold text-purple-400">Ingress</span> : <span className="text-xs text-stone-600">-</span> },
    {
      key: "enabled",
      header: "Status",
      render: (r: ProxyRoute) => (
        <button onClick={() => handleToggle(r)}>
          <StatusBadge status={r.enabled ? "enabled" : "disabled"} />
        </button>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (r: ProxyRoute) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(r)} className="text-sm font-medium text-orange-400 hover:text-orange-300 transition-colors">Edit</button>
          {r.k8s_ingress_enabled && (
            <button
              onClick={() => handleRowSync(r.id, r.name)}
              disabled={syncingRowId === r.id}
              className="text-sm font-medium text-purple-400 hover:text-purple-300 transition-colors disabled:opacity-50"
            >
              {syncingRowId === r.id ? "..." : "Sync"}
            </button>
          )}
          <button onClick={() => setConfirmDelete(r.id)} className="text-sm font-medium text-red-400 hover:text-red-300 transition-colors">Delete</button>
        </div>
      ),
    },
  ];

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">HTTP Routes</h1>
          <p className="text-sm text-stone-500 mt-1">Manage your reverse proxy routes</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={handleImportFile}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="btn-secondary"
          >
            {importing ? "Importing..." : "Import CSV"}
          </button>
          <button onClick={handleExport} className="btn-secondary">Export CSV</button>
          <button onClick={handleSyncAll} disabled={syncing} className="btn-secondary">
            {syncing ? "Syncing..." : "Sync All Ingresses"}
          </button>
          <button onClick={openCreate} className="btn-primary">Add Route</button>
        </div>
      </div>

      {syncMsg && (
        <div className={`mb-6 flex items-start justify-between rounded-md border p-3 text-sm ${syncMsg.kind === "ok" ? "border-emerald-800/40 bg-emerald-950/30 text-emerald-300" : "border-red-800/40 bg-red-950/30 text-red-300"}`}>
          <span>{syncMsg.text}</span>
          <button onClick={() => setSyncMsg(null)} className="ml-3 text-xs text-stone-500 hover:text-stone-300">dismiss</button>
        </div>
      )}

      {importResult && (
        <div className="mb-6 rounded-md border border-stone-800 bg-neutral-950 p-4">
          <div className="flex items-start justify-between">
            <div className="text-sm text-stone-300">
              <span className="font-semibold text-stone-100">Import complete.</span>{" "}
              <span className="text-emerald-400">{importResult.created} created</span>
              {", "}
              <span className="text-orange-400">{importResult.updated} updated</span>
              {", "}
              <span className="text-stone-500">{importResult.skipped} skipped</span>
            </div>
            <button onClick={() => setImportResult(null)} className="text-xs text-stone-500 hover:text-stone-300">dismiss</button>
          </div>
          {importResult.errors.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs font-mono text-red-400">
              {importResult.errors.slice(0, 20).map((err, i) => (
                <li key={i}>{err}</li>
              ))}
              {importResult.errors.length > 20 && (
                <li className="text-stone-500">… {importResult.errors.length - 20} more</li>
              )}
            </ul>
          )}
        </div>
      )}

      {routes.length === 0 ? (
        <EmptyState title="No routes yet" description="Create your first HTTP proxy route to get started." action={{ label: "Add Route", onClick: openCreate }} />
      ) : (
        <DataTable columns={columns} data={routes} keyField="id" />
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete Route"
        message="Are you sure you want to delete this route? This action cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Route" : "Add Route"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Name</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-stone-300">Host</label>
              <input required className="input-field" placeholder="example.com" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-stone-300">Path</label>
              <input className="input-field" value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-stone-300">Destination</label>
              <input required className="input-field" placeholder="127.0.0.1" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-stone-300">Port</label>
              <input required type="number" className="input-field" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Groups</label>
            <input className="input-field" placeholder="e.g. network-team, devops (comma-separated, empty = all)" value={form.groups} onChange={(e) => setForm({ ...form, groups: e.target.value })} />
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.ssl_enabled} onChange={(e) => setForm({ ...form, ssl_enabled: e.target.checked })} />
              SSL Enabled
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              Enabled
            </label>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Uploaded Cert Name (optional)</label>
            <input
              className="input-field"
              placeholder="e.g. wild-psuccso-org-tls"
              value={form.ssl_cert_name}
              onChange={(e) => setForm({ ...form, ssl_cert_name: e.target.value })}
            />
            <p className="mt-1 text-xs text-stone-600">
              Reference a cert uploaded under <code>TLS Certificates</code>. Leave empty to use path fields below (or no TLS).
            </p>
          </div>
          {form.ssl_enabled && !form.ssl_cert_name && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">SSL Cert Path</label>
                <input className="input-field" value={form.ssl_cert_path} onChange={(e) => setForm({ ...form, ssl_cert_path: e.target.value })} />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">SSL Key Path</label>
                <input className="input-field" value={form.ssl_key_path} onChange={(e) => setForm({ ...form, ssl_key_path: e.target.value })} />
              </div>
            </div>
          )}
          <div className="border-t border-stone-800/20 pt-4 mt-4">
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer font-medium">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-purple-500 focus:ring-purple-500/50" checked={form.k8s_ingress_enabled} onChange={(e) => setForm({ ...form, k8s_ingress_enabled: e.target.checked })} />
              Manage Kubernetes Ingress
            </label>
            {form.k8s_ingress_enabled && (
              <div className="mt-3 space-y-3 rounded-xl bg-neutral-950/50 p-4 border border-stone-800/20">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-stone-400">Cloudflare Proxy</label>
                    <select className="input-field text-sm" value={form.k8s_cloudflare_proxied} onChange={(e) => setForm({ ...form, k8s_cloudflare_proxied: e.target.value })}>
                      <option value="default">Use Default</option>
                      <option value="on">On</option>
                      <option value="off">Off</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-stone-400">Cluster Issuer Override</label>
                    <input className="input-field text-sm" placeholder="(use default)" value={form.k8s_cluster_issuer} onChange={(e) => setForm({ ...form, k8s_cluster_issuer: e.target.value })} />
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
                    <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-purple-500 focus:ring-purple-500/50" checked={form.k8s_cert_manager_enabled} onChange={(e) => setForm({ ...form, k8s_cert_manager_enabled: e.target.checked })} />
                    Cert-Manager TLS
                  </label>
                  <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
                    <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-purple-500 focus:ring-purple-500/50" checked={form.k8s_authentik_enabled} onChange={(e) => setForm({ ...form, k8s_authentik_enabled: e.target.checked })} />
                    Authentik Auth
                  </label>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-stone-400">Body Size Limit</label>
                    <input className="input-field text-sm" placeholder="e.g. 50m" value={form.k8s_proxy_body_size} onChange={(e) => setForm({ ...form, k8s_proxy_body_size: e.target.value })} />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-stone-400">Connect Timeout</label>
                    <input className="input-field text-sm" placeholder="e.g. 600" value={form.k8s_proxy_connect_timeout} onChange={(e) => setForm({ ...form, k8s_proxy_connect_timeout: e.target.value })} />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-stone-400">Read Timeout</label>
                    <input className="input-field text-sm" placeholder="e.g. 600" value={form.k8s_proxy_read_timeout} onChange={(e) => setForm({ ...form, k8s_proxy_read_timeout: e.target.value })} />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-stone-400">Send Timeout</label>
                    <input className="input-field text-sm" placeholder="e.g. 600" value={form.k8s_proxy_send_timeout} onChange={(e) => setForm({ ...form, k8s_proxy_send_timeout: e.target.value })} />
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3 pt-3">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? "Saving..." : "Save"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
