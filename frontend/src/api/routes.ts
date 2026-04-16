import { get, post, put, del } from "./client";
import type { ProxyRoute, PaginatedResponse } from "../types";

export function listRoutes(
  page = 1,
  perPage = 50,
): Promise<PaginatedResponse<ProxyRoute>> {
  return get(`/routes?page=${page}&per_page=${perPage}`);
}

export function getRoute(id: string): Promise<ProxyRoute> {
  return get(`/routes/${id}`);
}

export function createRoute(
  data: Omit<ProxyRoute, "id" | "created_at" | "updated_at">,
): Promise<ProxyRoute> {
  return post("/routes", data);
}

export function updateRoute(
  id: string,
  data: Partial<ProxyRoute>,
): Promise<ProxyRoute> {
  return put(`/routes/${id}`, data);
}

export function deleteRoute(id: string): Promise<void> {
  return del(`/routes/${id}`);
}

export function syncIngress(id: string): Promise<{ message: string }> {
  return post(`/routes/${id}/sync-ingress`);
}

const API_BASE = (import.meta.env.VITE_API_URL || "") + "/api/v1";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("pikatunnel_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function exportRoutesCsv(): Promise<void> {
  const res = await fetch(`${API_BASE}/routes/export.csv`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "routes.csv";
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

export async function importRoutesCsv(csvText: string): Promise<ImportResult> {
  const res = await fetch(`${API_BASE}/routes/import`, {
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
