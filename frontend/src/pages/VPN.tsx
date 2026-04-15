import { useEffect, useState, useCallback, type FormEvent } from "react";
import { listVPNs, createVPN, updateVPN, deleteVPN, connectVPN, disconnectVPN } from "../api/vpn";
import type { VPNConfig } from "../types";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";
import ConfirmDialog from "../components/ConfirmDialog";
import Toast from "../components/Toast";

type FormData = {
  name: string;
  vpn_type: string;
  enabled: boolean;
  ovpn_config: string;
};

const emptyForm: FormData = {
  name: "",
  vpn_type: "pritunl",
  enabled: true,
  ovpn_config: "",
};

export default function VPN() {
  const [vpns, setVpns] = useState<VPNConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<VPNConfig | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "info" | "error" } | null>(null);

  async function load() {
    try {
      const res = await listVPNs();
      setVpns(res);
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

  function openEdit(vpn: VPNConfig) {
    setEditing(vpn);
    setForm({
      name: vpn.name,
      vpn_type: vpn.vpn_type,
      enabled: vpn.enabled,
      ovpn_config: (vpn.config_data?.ovpn_config as string) || "",
    });
    setModalOpen(true);
  }

  const clearToast = useCallback(() => setToast(null), []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        vpn_type: form.vpn_type,
        enabled: form.enabled,
        config_data: { ovpn_config: form.ovpn_config },
      };
      if (editing) {
        await updateVPN(editing.id, payload);
      } else {
        await createVPN(payload);
      }
      setModalOpen(false);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function handleConnect(id: string) {
    setActionLoading(id);
    try {
      await connectVPN(id);
      await load();
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDisconnect(id: string) {
    setActionLoading(id);
    try {
      await disconnectVPN(id);
      await load();
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDelete(id: string) {
    await deleteVPN(id);
    setConfirmDelete(null);
    await load();
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setForm({ ...form, ovpn_config: reader.result as string });
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">VPN Connections</h1>
          <p className="text-sm text-stone-500 mt-1">Manage your VPN tunnels</p>
        </div>
        <button onClick={openCreate} className="btn-primary">Add VPN Config</button>
      </div>

      {vpns.length === 0 ? (
        <EmptyState title="No VPN configs yet" description="Add a VPN configuration to get started." action={{ label: "Add VPN Config", onClick: openCreate }} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {vpns.map((vpn) => (
            <div key={vpn.id} className="card group hover:border-stone-700/30 transition-all duration-200">
              <div className="mb-4 flex items-start justify-between">
                <div>
                  <h3 className="font-bold text-stone-100">{vpn.name}</h3>
                  <p className="text-sm text-stone-500 capitalize">{vpn.vpn_type}</p>
                </div>
                <StatusBadge status={vpn.status} />
              </div>
              {typeof vpn.config_data?.ovpn_config === "string" && (
                <p className="mb-3 text-xs text-stone-600 truncate font-mono">
                  {vpn.config_data.ovpn_config.split("\n").find((l) => l.startsWith("remote ")) || "Profile loaded"}
                </p>
              )}
              <div className="flex gap-2">
                {vpn.status === "connected" ? (
                  <button
                    onClick={() => handleDisconnect(vpn.id)}
                    disabled={actionLoading === vpn.id}
                    className="btn-secondary flex-1 text-sm"
                  >
                    {actionLoading === vpn.id ? "..." : "Disconnect"}
                  </button>
                ) : (
                  <button
                    onClick={() => handleConnect(vpn.id)}
                    disabled={actionLoading === vpn.id || vpn.status === "connecting"}
                    className="btn-primary flex-1 text-sm"
                  >
                    {actionLoading === vpn.id ? "..." : "Connect"}
                  </button>
                )}
                <button onClick={() => openEdit(vpn)} className="btn-secondary text-sm">Edit</button>
                <button onClick={() => setConfirmDelete(vpn.id)} className="btn-danger text-sm">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete VPN Config"
        message="Are you sure you want to delete this VPN configuration?"
        confirmLabel="Delete"
        danger
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />

      {toast && <Toast message={toast.message} type={toast.type} onClose={clearToast} />}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit VPN Config" : "Add VPN Config"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Name</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">VPN Type</label>
            <select className="input-field" value={form.vpn_type} onChange={(e) => setForm({ ...form, vpn_type: e.target.value })}>
              <option value="pritunl">Pritunl</option>
              <option value="wireguard">WireGuard</option>
              <option value="openvpn">OpenVPN</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
            <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            Enabled
          </label>
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-sm font-medium text-stone-300">OpenVPN Config</label>
              <label className="text-xs text-orange-400 hover:text-orange-300 cursor-pointer transition-colors">
                Upload .ovpn
                <input type="file" accept=".ovpn,.conf,.tar" className="hidden" onChange={handleFileUpload} />
              </label>
            </div>
            <textarea
              rows={10}
              className="input-field font-mono text-xs leading-relaxed"
              placeholder="Paste your .ovpn config here or upload a file..."
              value={form.ovpn_config}
              onChange={(e) => setForm({ ...form, ovpn_config: e.target.value })}
            />
            {form.ovpn_config && (
              <p className="mt-1 text-xs text-stone-600">
                {form.ovpn_config.split("\n").length} lines
              </p>
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
