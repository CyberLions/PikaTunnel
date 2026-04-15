import { get, put, post, del } from "./client";

export interface ClusterSettings {
  id: string;
  k8s_api_url: string | null;
  k8s_namespace: string;
  k8s_in_cluster: boolean;
  default_ingress_class: string;
  default_cluster_issuer: string;
  default_cloudflare_proxied: boolean;
  backend_service_name: string;
  backend_service_port: number;
  authentik_outpost_url: string | null;
  authentik_signin_url: string | null;
  authentik_response_headers: string;
  authentik_auth_snippet: string | null;
  has_token: boolean;
  has_ca_cert: boolean;
}

export function getClusterSettings(): Promise<ClusterSettings> {
  return get("/cluster/settings");
}

export function updateClusterSettings(data: Record<string, unknown>): Promise<ClusterSettings> {
  return put("/cluster/settings", data);
}

export function testClusterConnection(): Promise<{ connected: boolean; error?: string; version?: string }> {
  return post("/cluster/settings/test-connection");
}

export function clearCredentials(): Promise<void> {
  return del("/cluster/settings/credentials");
}
