import { get, post, put, del } from "./client";
import type { StreamRoute, PaginatedResponse } from "../types";

export function listStreams(
  page = 1,
  perPage = 50,
): Promise<PaginatedResponse<StreamRoute>> {
  return get(`/streams?page=${page}&per_page=${perPage}`);
}

export function getStream(id: string): Promise<StreamRoute> {
  return get(`/streams/${id}`);
}

export function createStream(
  data: Omit<StreamRoute, "id" | "created_at" | "updated_at">,
): Promise<StreamRoute> {
  return post("/streams", data);
}

export function updateStream(
  id: string,
  data: Partial<StreamRoute>,
): Promise<StreamRoute> {
  return put(`/streams/${id}`, data);
}

export function deleteStream(id: string): Promise<void> {
  return del(`/streams/${id}`);
}
