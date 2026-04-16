import { useEffect, useState, useCallback, useRef, type FormEvent } from "react";
import { listVPNs, createVPN, updateVPN, deleteVPN, connectVPN, disconnectVPN, getVPNLogs } from "../api/vpn";
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
  autostart: boolean;
  ovpn_config: string;
  wg_config: string;
};

const emptyForm: FormData = {
  name: "",
  vpn_type: "openvpn",
  enabled: true,
  autostart: false,
  ovpn_config: "",
  wg_config: "",
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
  const [logsFor, setLogsFor] = useState<VPNConfig | null>(null);
  const [logsText, setLogsText] = useState<string>("");
  const [logsLoading, setLogsLoading] = useState(false);
  const logsBodyRef = useRef<HTMLPreElement | null>(null);

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

  const hasActive = vpns.some((v) => v.status === "connecting");
  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => {
      listVPNs().then(setVpns).catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [hasActive]);

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
      autostart: vpn.autostart ?? false,
      ovpn_config: (vpn.config_data?.ovpn_config as string) || "",
      wg_config: (vpn.config_data?.wg_config as string) || "",
    });
    setModalOpen(true);
  }

  const clearToast = useCallback(() => setToast(null), []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const config_data =
        form.vpn_type === "wireguard"
          ? { wg_config: form.wg_config }
          : { ovpn_config: form.ovpn_config };
      const payload = {
        name: form.name,
        vpn_type: form.vpn_type,
        enabled: form.enabled,
        autostart: form.autostart,
        config_data,
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

  const fetchLogs = useCallback(async (id: string) => {
    try {
      const res = await getVPNLogs(id);
      setLogsText(res.logs || "(empty)");
      requestAnimationFrame(() => {
        const el = logsBodyRef.current;
        if (el) el.scrollTop = el.scrollHeight;
      });
    } catch (err) {
      setLogsText(`Error fetching logs: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, []);

  function openLogs(vpn: VPNConfig) {
    setLogsFor(vpn);
    setLogsText("");
    setLogsLoading(true);
    fetchLogs(vpn.id).finally(() => setLogsLoading(false));
  }

  useEffect(() => {
    if (!logsFor) return;
    const timer = setInterval(() => fetchLogs(logsFor.id), 3000);
    return () => clearInterval(timer);
  }, [logsFor, fetchLogs]);

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      if (form.vpn_type === "wireguard") {
        setForm({ ...form, wg_config: text });
      } else {
        setForm({ ...form, ovpn_config: text });
      }
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
              {vpn.autostart && vpn.reconnect_suspended_until && new Date(vpn.reconnect_suspended_until) > new Date() && (
                <p className="mb-3 text-xs text-amber-400">
                  Autoreconnect paused until {new Date(vpn.reconnect_suspended_until).toLocaleTimeString()}
                </p>
              )}
              {typeof vpn.config_data?.ovpn_config === "string" && (
                <p className="mb-3 text-xs text-stone-600 truncate font-mono">
                  {vpn.config_data.ovpn_config.split("\n").find((l) => l.startsWith("remote ")) || "Profile loaded"}
                </p>
              )}
              {typeof vpn.config_data?.wg_config === "string" && (
                <p className="mb-3 text-xs text-stone-600 truncate font-mono">
                  {vpn.config_data.wg_config.split("\n").find((l) => l.trim().startsWith("Endpoint")) || "Profile loaded"}
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
                <button onClick={() => openLogs(vpn)} className="btn-secondary text-sm">Logs</button>
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

      <Modal open={logsFor !== null} onClose={() => setLogsFor(null)} title={logsFor ? `Logs — ${logsFor.name}` : "Logs"}>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-stone-500">
            <span>Auto-refreshing every 3s</span>
            <button
              className="text-orange-400 hover:text-orange-300"
              onClick={() => logsFor && fetchLogs(logsFor.id)}
            >
              Refresh now
            </button>
          </div>
          <pre
            ref={logsBodyRef}
            className="max-h-[60vh] overflow-auto rounded border border-stone-800 bg-neutral-950 p-3 text-xs font-mono text-stone-300 whitespace-pre-wrap"
          >
            {logsLoading && !logsText ? "Loading..." : logsText}
          </pre>
        </div>
      </Modal>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? "Edit VPN Config" : "Add VPN Config"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Name</label>
            <input required className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">VPN Type</label>
            <select className="input-field" value={form.vpn_type} onChange={(e) => setForm({ ...form, vpn_type: e.target.value })}>
              <option value="openvpn">OpenVPN</option>
              <option value="wireguard">WireGuard</option>
            </select>
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              Enabled
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-300 cursor-pointer" title="Connect automatically when the backend starts">
              <input type="checkbox" className="rounded border-stone-600 bg-neutral-900 text-orange-500 focus:ring-orange-500/50" checked={form.autostart} onChange={(e) => setForm({ ...form, autostart: e.target.checked })} />
              Autostart on boot
            </label>
          </div>
          {form.vpn_type === "wireguard" ? (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-sm font-medium text-stone-300">WireGuard Config</label>
                <label className="text-xs text-orange-400 hover:text-orange-300 cursor-pointer transition-colors">
                  Upload .conf
                  <input type="file" accept=".conf" className="hidden" onChange={handleFileUpload} />
                </label>
              </div>
              <textarea
                rows={10}
                className="input-field font-mono text-xs leading-relaxed"
                placeholder="Paste your WireGuard config here or upload a .conf file..."
                value={form.wg_config}
                onChange={(e) => setForm({ ...form, wg_config: e.target.value })}
              />
              {form.wg_config && (
                <p className="mt-1 text-xs text-stone-600">
                  {form.wg_config.split("\n").length} lines
                </p>
              )}
            </div>
          ) : (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-sm font-medium text-stone-300">OpenVPN Config</label>
                <label className="text-xs text-orange-400 hover:text-orange-300 cursor-pointer transition-colors">
                  Upload .ovpn
                  <input type="file" accept=".ovpn,.conf" className="hidden" onChange={handleFileUpload} />
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
