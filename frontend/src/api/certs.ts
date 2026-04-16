import { get, post, put, del } from "./client";
import type { TLSCertificate, TLSCertificateSummary } from "../types";

export function listCerts(): Promise<TLSCertificateSummary[]> {
  return get("/certs");
}

export function getCert(id: string): Promise<TLSCertificate> {
  return get(`/certs/${id}`);
}

export type CertCreatePayload = {
  name: string;
  description?: string;
} & (
  | { cert_pem: string; key_pem: string; cert_path?: undefined; key_path?: undefined }
  | { cert_path: string; key_path: string; cert_pem?: undefined; key_pem?: undefined }
);

export function createCert(data: CertCreatePayload): Promise<TLSCertificate> {
  return post("/certs", data);
}

export function updateCert(
  id: string,
  data: {
    cert_pem?: string;
    key_pem?: string;
    cert_path?: string;
    key_path?: string;
    description?: string;
  },
): Promise<TLSCertificate> {
  return put(`/certs/${id}`, data);
}

export function deleteCert(id: string): Promise<void> {
  return del(`/certs/${id}`);
}
