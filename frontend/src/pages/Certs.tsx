import { useEffect, useState, type FormEvent } from "react";
import { listCerts, createCert, deleteCert } from "../api/certs";
import type { TLSCertificateSummary } from "../types";
import Modal from "../components/Modal";
import LoadingSpinner from "../components/LoadingSpinner";
import EmptyState from "../components/EmptyState";
import ConfirmDialog from "../components/ConfirmDialog";

type FormData = {
  name: string;
  description: string;
  cert_pem: string;
  key_pem: string;
};

const emptyForm: FormData = { name: "", description: "", cert_pem: "", key_pem: "" };

export default function Certs() {
  const [certs, setCerts] = useState<TLSCertificateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
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
    setForm(emptyForm);
    setError(null);
    setModalOpen(true);
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
      await createCert(form);
      setModalOpen(false);
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
                <button onClick={() => setConfirmDelete(c.id)} className="text-sm font-medium text-red-400 hover:text-red-300">Delete</button>
              </div>
              {c.description && <p className="text-sm text-stone-400 mb-2">{c.description}</p>}
              <p className="text-xs text-stone-600">Uploaded {new Date(c.created_at).toLocaleDateString()}</p>
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Upload TLS Certificate">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-stone-300">Name</label>
            <input
              required
              className="input-field"
              placeholder="wild-psuccso-org-tls"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <p className="mt-1 text-xs text-stone-600">Unique identifier. Routes reference this value in <code>ssl_cert_name</code>.</p>
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
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-sm font-medium text-stone-300">Certificate (PEM)</label>
              <label className="text-xs text-orange-400 hover:text-orange-300 cursor-pointer">
                Upload .crt / .pem
                <input type="file" accept=".crt,.pem,.cer" className="hidden" onChange={(e) => handleFile("cert_pem", e)} />
              </label>
            </div>
            <textarea
              required
              rows={6}
              className="input-field font-mono text-xs"
              placeholder="-----BEGIN CERTIFICATE-----"
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
              required
              rows={6}
              className="input-field font-mono text-xs"
              placeholder="-----BEGIN PRIVATE KEY-----"
              value={form.key_pem}
              onChange={(e) => setForm({ ...form, key_pem: e.target.value })}
            />
            <p className="mt-1 text-xs text-stone-600">Stored server-side; never returned over the API after upload.</p>
          </div>
          <div className="flex justify-end gap-3 pt-3">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">{saving ? "Uploading..." : "Upload"}</button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
