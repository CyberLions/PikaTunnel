import { useEffect, useState, type FormEvent } from "react";
import { listVPNs, createVPN, deleteVPN, connectVPN, disconnectVPN } from "../api/vpn";
import type { VPNConfig } from "../types";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";

type FormData = {
  name: string;
  vpn_type: string;
  enabled: boolean;
  config_data: string;
};

const emptyForm: FormData = {
  name: "",
  vpn_type: "pritunl",
  enabled: true,
  config_data: "{}",
};

export default function VPN() {
  const [vpns, setVpns] = useState<VPNConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

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
    setForm(emptyForm);
    setModalOpen(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      let configData: Record<string, unknown>;
      try {
        configData = JSON.parse(form.config_data);
      } catch {
        alert("Invalid JSON in config data");
        return;
      }
      await createVPN({
        name: form.name,
        vpn_type: form.vpn_type,
        enabled: form.enabled,
        config_data: configData,
      });
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
    if (!confirm("Delete this VPN config?")) return;
    await deleteVPN(id);
    await load();
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">VPN Connections</h1>
        <button onClick={openCreate} className="btn-primary">Add VPN Config</button>
      </div>

      {vpns.length === 0 ? (
        <EmptyState title="No VPN configs" description="Add a VPN configuration to get started." action={{ label: "Add VPN Config", onClick: openCreate }} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {vpns.map((vpn) => (
            <div key={vpn.id} className="card">
              <div className="mb-4 flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-slate-100">{vpn.name}</h3>
                  <p className="text-sm text-slate-500">{vpn.vpn_type}</p>
                </div>
                <StatusBadge status={vpn.status} />
              </div>
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
                <button onClick={() => handleDelete(vpn.id)} className="btn-danger text-sm">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Add VPN Config">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-slate-400">Name *</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">VPN Type</label>
            <select className="input-field" value={form.vpn_type} onChange={(e) => setForm({ ...form, vpn_type: e.target.value })}>
              <option value="pritunl">Pritunl</option>
              <option value="wireguard">WireGuard</option>
              <option value="openvpn">OpenVPN</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" className="rounded border-slate-600" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            Enabled
          </label>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Config Data (JSON)</label>
            <textarea
              rows={6}
              className="input-field font-mono text-sm"
              value={form.config_data}
              onChange={(e) => setForm({ ...form, config_data: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? "Saving..." : "Save"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
