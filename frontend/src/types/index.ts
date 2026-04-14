export interface ProxyRoute {
  id: string;
  name: string;
  host: string;
  path: string;
  destination: string;
  port: number;
  ssl_enabled: boolean;
  ssl_cert_path: string | null;
  ssl_key_path: string | null;
  enabled: boolean;
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
  created_at: string;
  updated_at: string;
}

export interface VPNConfig {
  id: string;
  name: string;
  vpn_type: string;
  enabled: boolean;
  config_data: Record<string, unknown>;
  status: "disconnected" | "connecting" | "connected" | "error";
  created_at: string;
  updated_at: string;
}

export interface OIDCProvider {
  id: string;
  name: string;
  issuer_url: string;
  client_id: string;
  scopes: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface NginxStatus {
  running: boolean;
  config_valid: boolean;
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
