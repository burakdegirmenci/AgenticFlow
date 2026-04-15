import type { NodeCatalogEntry } from "@/types/node";

import { apiClient } from "./client";

export async function listNodes(): Promise<NodeCatalogEntry[]> {
  const { data } = await apiClient.get<NodeCatalogEntry[]>("/nodes");
  return data;
}

export async function getNode(typeId: string): Promise<NodeCatalogEntry> {
  const { data } = await apiClient.get<NodeCatalogEntry>(`/nodes/${typeId}`);
  return data;
}
