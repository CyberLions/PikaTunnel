import { get, post, put, del } from "./client";
import type { StreamRoute, PaginatedResponse } from "../types";

export function listStreams(
  page = 1,
  perPage = 50,
): Promise<PaginatedResponse<StreamRoute>> {
  return get(`/streams?page=${page}&per_page=${perPage}`);
}

export function getStream(id: string): Promise<StreamRoute> {
  return get(`/streams/${id}`);
}

export function createStream(
  data: Omit<StreamRoute, "id" | "created_at" | "updated_at">,
): Promise<StreamRoute> {
  return post("/streams", data);
}

export function updateStream(
  id: string,
  data: Partial<StreamRoute>,
): Promise<StreamRoute> {
  return put(`/streams/${id}`, data);
}

export function deleteStream(id: string): Promise<void> {
  return del(`/streams/${id}`);
}

const API_BASE = (import.meta.env.VITE_API_URL || "") + "/api/v1";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("pikatunnel_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function exportStreamsCsv(): Promise<void> {
  const res = await fetch(`${API_BASE}/streams/export.csv`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "streams.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export type ImportResult = {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
};

export async function importStreamsCsv(csvText: string): Promise<ImportResult> {
  const res = await fetch(`${API_BASE}/streams/import`, {
    method: "POST",
    headers: { "Content-Type": "text/csv", ...authHeaders() },
    body: csvText,
  });
  if (!res.ok) {
    let detail = `Import failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* noop */
    }
    throw new Error(detail);
  }
  return res.json();
}
