import type { Execution, ExecutionDetail } from "@/types/execution";

import { apiClient } from "./client";

export async function listExecutions(params?: {
  workflow_id?: number;
  status?: string;
  trigger_type?: string;
  since?: string;
  search?: string;
  limit?: number;
}): Promise<Execution[]> {
  // Strip empty strings so backend doesn't see them as filters.
  const cleaned: Record<string, unknown> = {};
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") {
        cleaned[k] = v;
      }
    }
  }
  const { data } = await apiClient.get<Execution[]>("/executions", {
    params: cleaned,
  });
  return data;
}

export async function getExecution(id: number): Promise<ExecutionDetail> {
  const { data } = await apiClient.get<ExecutionDetail>(`/executions/${id}`);
  return data;
}
