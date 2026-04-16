export interface ProxyRoute {
  id: string;
  name: string;
  host: string;
  path: string;
  destination: string;
  port: number;
  ssl_enabled: boolean;
  ssl_cert_name: string | null;
  ssl_cert_path: string | null;
  ssl_key_path: string | null;
  enabled: boolean;
  groups: string;
  k8s_ingress_enabled: boolean;
  k8s_cloudflare_proxied: boolean | null;
  k8s_cert_manager_enabled: boolean;
  k8s_cluster_issuer: string | null;
  k8s_authentik_enabled: boolean;
  k8s_proxy_body_size: string | null;
  k8s_proxy_read_timeout: string | null;
  k8s_proxy_send_timeout: string | null;
  k8s_proxy_connect_timeout: string | null;
  k8s_custom_annotations: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

export interface StreamRoute {
  id: string;
  name: string;
  destination: string;
  port: number;
  listen_port: number;
  protocol: "tcp" | "udp";
  proxy_protocol: boolean;
  enabled: boolean;
  groups: string;
  created_at: string;
  updated_at: string;
}

export interface VPNConfig {
  id: string;
  name: string;
  vpn_type: string;
  enabled: boolean;
  autostart: boolean;
  config_data: Record<string, unknown>;
  status: "disconnected" | "connecting" | "connected" | "error";
  created_at: string;
  updated_at: string;
}

export interface TLSCertificateSummary {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface TLSCertificate extends TLSCertificateSummary {
  cert_pem: string;
  has_key: boolean;
}

export interface OIDCProvider {
  id: string;
  name: string;
  issuer_url: string;
  client_id: string;
  scopes: string;
  groups_claim: string;
  admin_group: string;
  enabled: boolean;
  source: string;
  read_only: boolean;
  created_at: string;
  updated_at: string;
}

export interface NginxStatus {
  running: boolean;
  pid?: number | null;
  config_valid: boolean;
  config_error?: string | null;
}

export interface HealthStatus {
  status: string;
  database: boolean;
  nginx: NginxStatus;
  vpn: { enabled: boolean; status: string };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}
