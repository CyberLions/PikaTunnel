import { get, post } from "./client";
import type { NginxStatus } from "../types";

export function getNginxStatus(): Promise<NginxStatus> {
  return get("/nginx/status");
}

export function reloadNginx(): Promise<{ message: string }> {
  return post("/nginx/reload");
}

export function previewConfig(): Promise<{ http_config: string; stream_config: string }> {
  return get("/nginx/config");
}
