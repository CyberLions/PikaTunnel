import { useEffect, useState, type FormEvent } from "react";
import { listCerts, createCert, updateCert, deleteCert, getCert } from "../api/certs";
import type { TLSCertificateSummary } from "../types";
import Modal from "../components/Modal";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";
import ConfirmDialog from "../components/ConfirmDialog";

type FormData = {
  name: string;
  description: string;
  source: "inline" | "path";
  cert_pem: string;
  key_pem: string;
  cert_path: string;
  key_path: string;
};

const emptyForm: FormData = {
  name: "",
  description: "",
  source: "inline",
  cert_pem: "",
  key_pem: "",
  cert_path: "",
  key_path: "",
};

export default function Certs() {
  const [certs, setCerts] = useState<TLSCertificateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setCerts(await listCerts());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setError(null);
    setModalOpen(true);
  }

  async function openEdit(id: string) {
    setError(null);
    try {
      const cert = await getCert(id);
      setEditingId(id);
      setForm({
        name: cert.name,
        description: cert.description || "",
        source: cert.source,
        cert_pem: cert.cert_pem || "",
        key_pem: "", // never returned; blank unless user wants to rotate
        cert_path: cert.cert_path || "",
        key_path: cert.key_path || "",
      });
      setModalOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleFile(
    field: "cert_pem" | "key_pem",
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const text = await file.text();
    setForm((f) => ({ ...f, [field]: text }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        // Edit: send only fields appropriate for the chosen source.
        const payload: {
          description?: string;
          cert_pem?: string;
          key_pem?: string;
          cert_path?: string;
          key_path?: string;
        } = { description: form.description };
        if (form.source === "path") {
          payload.cert_path = form.cert_path;
          payload.key_path = form.key_path;
        } else {
          if (form.cert_pem) payload.cert_pem = form.cert_pem;
          if (form.key_pem) payload.key_pem = form.key_pem;
        }
        await updateCert(editingId, payload);
      } else if (form.source === "path") {
        await createCert({
          name: form.name,
          description: form.description,
          cert_path: form.cert_path,
          key_path: form.key_path,
        });
      } else {
        await createCert({
          name: form.name,
          description: form.description,
          cert_pem: form.cert_pem,
          key_pem: form.key_pem,
        });
      }
      setModalOpen(false);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteCert(id);
      setConfirmDelete(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConfirmDelete(null);
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">TLS Certificates</h1>
          <p className="text-sm text-stone-500 mt-1">
            Upload PEM cert/key pairs and reference them from routes by name
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary">Upload Cert</button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-xs text-stone-500 hover:text-stone-300">dismiss</button>
        </div>
      )}

      {certs.length === 0 ? (
        <EmptyState
          title="No certificates uploaded"
          description="Upload a PEM cert and private key. Routes reference certs by name."
          action={{ label: "Upload Cert", onClick: openCreate }}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {certs.map((c) => (
            <div key={c.id} className="card">
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-bold text-stone-100 break-all">{c.name}</h3>
                <div className="flex gap-3">
                  <button onClick={() => openEdit(c.id)} className="text-sm font-medium text-orange-400 hover:text-orange-300">Edit</button>
                  <button onClick={() => setConfirmDelete(c.id)} className="text-sm font-medium text-red-400 hover:text-red-300">Delete</button>
                </div>
              </div>
              {c.description && <p className="text-sm text-stone-400 mb-2">{c.description}</p>}
              <p className="text-xs text-stone-500">
                <span className={c.source === "path" ? "text-purple-400" : "text-emerald-400"}>
                  {c.source === "path" ? "Mounted" : "Inline"}
                </span>
                {c.source === "path" && c.cert_path && (
                  <span className="ml-2 font-mono text-stone-500 break-all">{c.cert_path}</span>
                )}
              </p>
              <p className="text-xs text-stone-600 mt-1">Added {new Date(c.created_at).toLocaleDateString()}</p>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title="Delete Certificate"
        message="This cannot be undone. Routes that reference this certificate by name will lose their TLS config."
        confirmLabel="Delete"
        danger
        onConfirm={() => confirmDelete && handleDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />

      <Modal open={modalOpen} onClose={() => { setModalOpen(false); setEditingId(null); }} title={editingId ? "Edit TLS Certificate" : "Upload TLS Certificate"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Name</label>
            <input
              required
              disabled={!!editingId}
              className="input-field disabled:opacity-60 disabled:cursor-not-allowed"
              placeholder="wild-psuccso-org-tls"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <p className="mt-1 text-xs text-stone-600">
              {editingId
                ? "Name is immutable — routes reference this cert by name. Delete + recreate to rename."
                : <>Unique identifier. Routes reference this value in <code>ssl_cert_name</code>.</>}
            </p>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Description</label>
            <input
              className="input-field"
              placeholder="*.psuccso.org wildcard, expires 2026-08"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Source</label>
            <div className="flex gap-4 text-sm text-stone-300">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="cert-source"
                  value="inline"
                  checked={form.source === "inline"}
                  onChange={() => setForm({ ...form, source: "inline" })}
                />
                Paste PEM (stored in DB)
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="cert-source"
                  value="path"
                  checked={form.source === "path"}
                  onChange={() => setForm({ ...form, source: "path" })}
                />
                Mounted file path (e.g. k8s secret volume)
              </label>
            </div>
          </div>
          {form.source === "inline" ? (
            <>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-sm font-medium text-stone-300">Certificate (PEM)</label>
                  <label className="text-xs text-orange-400 hover:text-orange-300 cursor-pointer">
                    Upload .crt / .pem
                    <input type="file" accept=".crt,.pem,.cer" className="hidden" onChange={(e) => handleFile("cert_pem", e)} />
                  </label>
                </div>
                <textarea
                  required={!editingId}
                  rows={6}
                  className="input-field font-mono text-xs"
                  placeholder={editingId ? "Leave blank to keep existing cert" : "-----BEGIN CERTIFICATE-----"}
                  value={form.cert_pem}
                  onChange={(e) => setForm({ ...form, cert_pem: e.target.value })}
                />
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-sm font-medium text-stone-300">Private Key (PEM)</label>
                  <label className="text-xs text-orange-400 hover:text-orange-300 cursor-pointer">
                    Upload .key / .pem
                    <input type="file" accept=".key,.pem" className="hidden" onChange={(e) => handleFile("key_pem", e)} />
                  </label>
                </div>
                <textarea
                  required={!editingId}
                  rows={6}
                  className="input-field font-mono text-xs"
                  placeholder={editingId ? "Leave blank to keep existing key" : "-----BEGIN PRIVATE KEY-----"}
                  value={form.key_pem}
                  onChange={(e) => setForm({ ...form, key_pem: e.target.value })}
                />
                <p className="mt-1 text-xs text-stone-600">
                  Stored server-side; never returned over the API.
                  {editingId && " Leave blank to keep the current key."}
                </p>
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">Certificate File Path</label>
                <input
                  required
                  className="input-field font-mono text-xs"
                  placeholder="/etc/nginx/secrets/wild-psuccso-org-tls/tls.crt"
                  value={form.cert_path}
                  onChange={(e) => setForm({ ...form, cert_path: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-stone-300">Private Key File Path</label>
                <input
                  required
                  className="input-field font-mono text-xs"
                  placeholder="/etc/nginx/secrets/wild-psuccso-org-tls/tls.key"
                  value={form.key_path}
                  onChange={(e) => setForm({ ...form, key_path: e.target.value })}
                />
                <p className="mt-1 text-xs text-stone-600">
                  Paths must be readable by nginx inside the pikatunnel pod. Mount the k8s secret as a volumeMount, then point here.
                  Key rotation is automatic — when the Secret updates, nginx will pick up the new file on its next reload.
                </p>
              </div>
            </>
          )}
          <div className="flex justify-end gap-3 pt-3">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? (editingId ? "Saving..." : "Uploading...") : (editingId ? "Save" : "Upload")}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
