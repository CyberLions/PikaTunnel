import { useEffect, useState, type FormEvent } from "react";
import { listRoutes, createRoute, updateRoute, deleteRoute } from "../api/routes";
import { reloadNginx } from "../api/nginx";
import type { ProxyRoute } from "../types";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";

type FormData = {
  name: string;
  host: string;
  path: string;
  destination: string;
  port: string;
  ssl_enabled: boolean;
  ssl_cert_path: string;
  ssl_key_path: string;
  enabled: boolean;
};

const emptyForm: FormData = {
  name: "",
  host: "",
  path: "/",
  destination: "",
  port: "80",
  ssl_enabled: false,
  ssl_cert_path: "",
  ssl_key_path: "",
  enabled: true,
};

export default function Routes() {
  const [routes, setRoutes] = useState<ProxyRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ProxyRoute | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);

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
      ssl_cert_path: route.ssl_cert_path || "",
      ssl_key_path: route.ssl_key_path || "",
      enabled: route.enabled,
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
        ssl_enabled: form.ssl_enabled,
        ssl_cert_path: form.ssl_cert_path || null,
        ssl_key_path: form.ssl_key_path || null,
        enabled: form.enabled,
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
    if (!confirm("Delete this route?")) return;
    await deleteRoute(id);
    await reloadNginx().catch(() => {});
    await load();
  }

  async function handleToggle(route: ProxyRoute) {
    await updateRoute(route.id, { enabled: !route.enabled });
    await reloadNginx().catch(() => {});
    await load();
  }

  const columns = [
    { key: "name", header: "Name", render: (r: ProxyRoute) => <span className="font-medium text-slate-100">{r.name}</span> },
    { key: "host", header: "Host", render: (r: ProxyRoute) => r.host },
    { key: "path", header: "Path", render: (r: ProxyRoute) => <code className="text-xs text-blue-400">{r.path}</code> },
    { key: "dest", header: "Destination", render: (r: ProxyRoute) => `${r.destination}:${r.port}` },
    { key: "ssl", header: "SSL", render: (r: ProxyRoute) => r.ssl_enabled ? <span className="text-green-400">Yes</span> : <span className="text-slate-500">No</span> },
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
          <button onClick={() => openEdit(r)} className="text-sm text-blue-400 hover:text-blue-300">Edit</button>
          <button onClick={() => handleDelete(r.id)} className="text-sm text-red-400 hover:text-red-300">Delete</button>
        </div>
      ),
    },
  ];

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">HTTP Routes</h1>
        <button onClick={openCreate} className="btn-primary">Add Route</button>
      </div>

      {routes.length === 0 ? (
        <EmptyState title="No routes" description="Create your first HTTP proxy route." action={{ label: "Add Route", onClick: openCreate }} />
      ) : (
        <DataTable columns={columns} data={routes} keyField="id" />
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Route" : "Add Route"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-slate-400">Name *</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm text-slate-400">Host *</label>
              <input required className="input-field" placeholder="example.com" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-400">Path</label>
              <input className="input-field" value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm text-slate-400">Destination *</label>
              <input required className="input-field" placeholder="127.0.0.1" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-400">Port *</label>
              <input required type="number" className="input-field" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" className="rounded border-slate-600" checked={form.ssl_enabled} onChange={(e) => setForm({ ...form, ssl_enabled: e.target.checked })} />
              SSL Enabled
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" className="rounded border-slate-600" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              Enabled
            </label>
          </div>
          {form.ssl_enabled && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm text-slate-400">SSL Cert Path</label>
                <input className="input-field" value={form.ssl_cert_path} onChange={(e) => setForm({ ...form, ssl_cert_path: e.target.value })} />
              </div>
              <div>
                <label className="mb-1 block text-sm text-slate-400">SSL Key Path</label>
                <input className="input-field" value={form.ssl_key_path} onChange={(e) => setForm({ ...form, ssl_key_path: e.target.value })} />
              </div>
            </div>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? "Saving..." : "Save"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
