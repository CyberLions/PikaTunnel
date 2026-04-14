import { get, post, put, del } from "./client";
import type { OIDCProvider } from "../types";

export function listProviders(): Promise<OIDCProvider[]> {
  return get("/auth/providers");
}

export function getProvider(id: string): Promise<OIDCProvider> {
  return get(`/auth/providers/${id}`);
}

export function createProvider(
  data: Omit<OIDCProvider, "id" | "created_at" | "updated_at"> & {
    client_secret: string;
  },
): Promise<OIDCProvider> {
  return post("/auth/providers", data);
}

export function updateProvider(
  id: string,
  data: Partial<OIDCProvider & { client_secret: string }>,
): Promise<OIDCProvider> {
  return put(`/auth/providers/${id}`, data);
}

export function deleteProvider(id: string): Promise<void> {
  return del(`/auth/providers/${id}`);
}
