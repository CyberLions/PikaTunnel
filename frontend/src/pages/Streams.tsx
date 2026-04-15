import { useEffect, useState, type FormEvent } from "react";
import { listStreams, createStream, updateStream, deleteStream } from "../api/streams";
import { reloadNginx } from "../api/nginx";
import type { StreamRoute } from "../types";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";
import ConfirmDialog from "../components/ConfirmDialog";

type FormData = {
  name: string;
  destination: string;
  port: string;
  listen_port: string;
  protocol: "tcp" | "udp";
  proxy_protocol: boolean;
  enabled: boolean;
};

const emptyForm: FormData = {
  name: "",
  destination: "",
  port: "0",
  listen_port: "0",
  protocol: "tcp",
  proxy_protocol: false,
  enabled: true,
};

export default function Streams() {
  const [streams, setStreams] = useState<StreamRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<StreamRoute | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  async function load() {
    try {
      const res = await listStreams();
      setStreams(res.items);
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

  function openEdit(stream: StreamRoute) {
    setEditing(stream);
    setForm({
      name: stream.name,
      destination: stream.destination,
      port: String(stream.port),
      listen_port: String(stream.listen_port),
      protocol: stream.protocol,
      proxy_protocol: stream.proxy_protocol,
      enabled: stream.enabled,
    });
    setModalOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        destination: form.destination,
        port: parseInt(form.port),
        listen_port: parseInt(form.listen_port),
        protocol: form.protocol,
        proxy_protocol: form.proxy_protocol,
        enabled: form.enabled,
      };
      if (editing) {
        await updateStream(editing.id, payload);
      } else {
        await createStream(payload);
      }
      await reloadNginx().catch(() => {});
      setModalOpen(false);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    await deleteStream(id);
    await reloadNginx().catch(() => {});
    setConfirmDelete(null);
    await load();
  }

  async function handleToggle(stream: StreamRoute) {
    await updateStream(stream.id, { enabled: !stream.enabled });
    await reloadNginx().catch(() => {});
    await load();
  }

  const columns = [
    { key: "name", header: "Name", render: (s: StreamRoute) => <span className="font-semibold text-stone-100">{s.name}</span> },
    { key: "dest", header: "Destination", render: (s: StreamRoute) => <span className="text-stone-300">{s.destination}</span> },
    { key: "port", header: "Port", render: (s: StreamRoute) => <span className="font-mono text-xs text-stone-400">{s.port}</span> },
    { key: "listen", header: "Listen Port", render: (s: StreamRoute) => <span className="font-mono text-xs text-orange-400">{s.listen_port}</span> },
    { key: "protocol", header: "Protocol", render: (s: StreamRoute) => <span className="uppercase text-xs font-bold text-stone-400 bg-stone-800/40 px-2 py-0.5 rounded-md">{s.protocol}</span> },
    { key: "pp", header: "Proxy Protocol", render: (s: StreamRoute) => s.proxy_protocol ? <span className="text-emerald-400 text-xs font-semibold">Yes</span> : <span className="text-stone-600 text-xs">No</span> },
    {
      key: "enabled",
      header: "Status",
      render: (s: StreamRoute) => (
        <button onClick={() => handleToggle(s)}>
          <StatusBadge status={s.enabled ? "enabled" : "disabled"} />
        </button>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (s: StreamRoute) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(s)} className="text-sm font-medium text-orange-400 hover:text-orange-300 transition-colors">Edit</button>
          <button onClick={() => setConfirmDelete(s.id)} className="text-sm font-medium text-red-400 hover:text-red-300 transition-colors">Delete</button>
        </div>
      ),
    },
  ];

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">Stream Routes</h1>
          <p className="text-sm text-stone-500 mt-1">TCP and UDP stream forwarding</p>
        </div>
        <button onClick={openCreate} className="btn-primary">Add Stream</button>
      </div>

      {streams.length === 0 ? (
        <EmptyState title="No stream routes yet" description="Create your first TCP/UDP stream route." action={{ label: "Add Stream", onClick: openCreate }} />
      ) : (
        <DataTable columns={columns} data={streams} keyField="id" />
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete Stream Route"
        message="Are you sure you want to delete this stream route? This action cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Stream" : "Add Stream"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Name</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Destination</label>
            <input required className="input-field" placeholder="10.0.0.1" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-stone-300">Port</label>
              <input required type="number" className="input-field" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-stone-300">Listen Port</label>
              <input required type="number" className="input-field" value={form.listen_port} onChange={(e) => setForm({ ...form, listen_port: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Protocol</label>
            <select className="input-field" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as "tcp" | "udp" })}>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
            </select>
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.proxy_protocol} onChange={(e) => setForm({ ...form, proxy_protocol: e.target.checked })} />
              Proxy Protocol
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              Enabled
            </label>
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
