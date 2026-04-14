import { useEffect, useState, type FormEvent } from "react";
import { listProviders, createProvider, updateProvider, deleteProvider } from "../api/auth";
import type { OIDCProvider } from "../types";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";

type FormData = {
  name: string;
  issuer_url: string;
  client_id: string;
  client_secret: string;
  scopes: string;
  enabled: boolean;
};

const emptyForm: FormData = {
  name: "",
  issuer_url: "",
  client_id: "",
  client_secret: "",
  scopes: "openid profile email",
  enabled: true,
};

export default function Auth() {
  const [providers, setProviders] = useState<OIDCProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OIDCProvider | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const res = await listProviders();
      setProviders(res);
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

  function openEdit(provider: OIDCProvider) {
    setEditing(provider);
    setForm({
      name: provider.name,
      issuer_url: provider.issuer_url,
      client_id: provider.client_id,
      client_secret: "",
      scopes: provider.scopes,
      enabled: provider.enabled,
    });
    setModalOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        issuer_url: form.issuer_url,
        client_id: form.client_id,
        client_secret: form.client_secret,
        scopes: form.scopes,
        enabled: form.enabled,
      };
      if (editing) {
        const updatePayload = form.client_secret ? payload : { ...payload, client_secret: undefined };
        await updateProvider(editing.id, updatePayload);
      } else {
        await createProvider(payload);
      }
      setModalOpen(false);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this OIDC provider?")) return;
    await deleteProvider(id);
    await load();
  }

  const columns = [
    { key: "name", header: "Name", render: (p: OIDCProvider) => <span className="font-medium text-slate-100">{p.name}</span> },
    { key: "issuer", header: "Issuer URL", render: (p: OIDCProvider) => <span className="text-xs text-slate-400">{p.issuer_url}</span> },
    { key: "client", header: "Client ID", render: (p: OIDCProvider) => <code className="text-xs">{p.client_id}</code> },
    { key: "scopes", header: "Scopes", render: (p: OIDCProvider) => p.scopes },
    {
      key: "enabled",
      header: "Status",
      render: (p: OIDCProvider) => <StatusBadge status={p.enabled ? "enabled" : "disabled"} />,
    },
    {
      key: "actions",
      header: "",
      render: (p: OIDCProvider) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(p)} className="text-sm text-blue-400 hover:text-blue-300">Edit</button>
          <button onClick={() => handleDelete(p.id)} className="text-sm text-red-400 hover:text-red-300">Delete</button>
        </div>
      ),
    },
  ];

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Authentication Providers</h1>
        <button onClick={openCreate} className="btn-primary">Add Provider</button>
      </div>

      {providers.length === 0 ? (
        <EmptyState title="No OIDC providers" description="Configure an OIDC provider for authentication." action={{ label: "Add Provider", onClick: openCreate }} />
      ) : (
        <DataTable columns={columns} data={providers} keyField="id" />
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit Provider" : "Add Provider"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-slate-400">Name *</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Issuer URL *</label>
            <input required type="url" className="input-field" placeholder="https://accounts.google.com" value={form.issuer_url} onChange={(e) => setForm({ ...form, issuer_url: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Client ID *</label>
            <input required className="input-field" value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Client Secret {editing ? "(leave blank to keep)" : "*"}</label>
            <input
              type="password"
              className="input-field"
              required={!editing}
              value={form.client_secret}
              onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Scopes</label>
            <input className="input-field" value={form.scopes} onChange={(e) => setForm({ ...form, scopes: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" className="rounded border-slate-600" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            Enabled
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? "Saving..." : "Save"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
