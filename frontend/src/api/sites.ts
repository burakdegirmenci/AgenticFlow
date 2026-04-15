import { apiClient } from "./client";

export interface Site {
  id: number;
  name: string;
  domain: string;
  created_at: string;
  updated_at: string;
}

export interface SiteCreatePayload {
  name: string;
  domain: string;
  uye_kodu: string;
}

export interface SiteUpdatePayload {
  name?: string;
  domain?: string;
  uye_kodu?: string;
}

export interface SiteConnectionTest {
  status: "ok" | "error";
  services: Record<string, boolean>;
  error?: string | null;
}

export async function listSites(): Promise<Site[]> {
  const { data } = await apiClient.get<Site[]>("/sites");
  return data;
}

export async function getSite(id: number): Promise<Site> {
  const { data } = await apiClient.get<Site>(`/sites/${id}`);
  return data;
}

export async function createSite(payload: SiteCreatePayload): Promise<Site> {
  const { data } = await apiClient.post<Site>("/sites", payload);
  return data;
}

export async function updateSite(id: number, payload: SiteUpdatePayload): Promise<Site> {
  const { data } = await apiClient.patch<Site>(`/sites/${id}`, payload);
  return data;
}

export async function deleteSite(id: number): Promise<void> {
  await apiClient.delete(`/sites/${id}`);
}

export async function testSiteConnection(id: number): Promise<SiteConnectionTest> {
  const { data } = await apiClient.post<SiteConnectionTest>(`/sites/${id}/test-connection`);
  return data;
}
