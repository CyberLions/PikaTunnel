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
