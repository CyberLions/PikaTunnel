import { get, post, put, del } from "./client";
import type { OIDCProvider } from "../types";

export interface OIDCProviderPayload {
  name: string;
  issuer_url: string;
  client_id: string;
  scopes: string;
  groups_claim: string;
  enabled: boolean;
  client_secret?: string;
}

export function listProviders(): Promise<OIDCProvider[]> {
  return get("/auth/providers");
}

export function getProvider(id: string): Promise<OIDCProvider> {
  return get(`/auth/providers/${id}`);
}

export function createProvider(
  data: OIDCProviderPayload & { client_secret: string },
): Promise<OIDCProvider> {
  return post("/auth/providers", data);
}

export function updateProvider(
  id: string,
  data: Partial<OIDCProviderPayload>,
): Promise<OIDCProvider> {
  return put(`/auth/providers/${id}`, data);
}

export function deleteProvider(id: string): Promise<void> {
  return del(`/auth/providers/${id}`);
}
