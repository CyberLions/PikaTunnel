import { get, post, put, del } from "./client";
import type { TLSCertificate, TLSCertificateSummary } from "../types";

export function listCerts(): Promise<TLSCertificateSummary[]> {
  return get("/certs");
}

export function getCert(id: string): Promise<TLSCertificate> {
  return get(`/certs/${id}`);
}

export function createCert(data: {
  name: string;
  cert_pem: string;
  key_pem: string;
  description?: string;
}): Promise<TLSCertificate> {
  return post("/certs", data);
}

export function updateCert(
  id: string,
  data: { cert_pem?: string; key_pem?: string; description?: string },
): Promise<TLSCertificate> {
  return put(`/certs/${id}`, data);
}

export function deleteCert(id: string): Promise<void> {
  return del(`/certs/${id}`);
}
