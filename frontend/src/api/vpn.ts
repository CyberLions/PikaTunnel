import { get, post, put, del } from "./client";
import type { VPNConfig } from "../types";

export function listVPNs(): Promise<VPNConfig[]> {
  return get("/vpn/config");
}

export function createVPN(
  data: Omit<VPNConfig, "id" | "created_at" | "updated_at" | "status">,
): Promise<VPNConfig> {
  return post("/vpn/config", data);
}

export function updateVPN(
  id: string,
  data: Partial<VPNConfig>,
): Promise<VPNConfig> {
  return put(`/vpn/config/${id}`, data);
}

export function deleteVPN(id: string): Promise<void> {
  return del(`/vpn/config/${id}`);
}

export function connectVPN(id: string): Promise<VPNConfig> {
  return post(`/vpn/config/${id}/connect`);
}

export function disconnectVPN(id: string): Promise<VPNConfig> {
  return post(`/vpn/config/${id}/disconnect`);
}

export function getVPNLogs(id: string): Promise<{ id: string; vpn_type: string; logs: string }> {
  return get(`/vpn/config/${id}/logs`);
}
