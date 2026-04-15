import { useEffect, useState, type FormEvent } from "react";
import { listRoutes, createRoute, updateRoute, deleteRoute } from "../api/routes";
import { reloadNginx } from "../api/nginx";
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
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

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
        <button onClick={openCreate} className="btn-primary">Add Route</button>
      </div>

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
          {form.ssl_enabled && (
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
          <div className="flex justify-end gap-3 pt-3">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? "Saving..." : "Save"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
