import type { Execution } from "@/types/execution";
import type { Workflow, WorkflowCreatePayload, WorkflowUpdatePayload } from "@/types/workflow";

import { apiClient } from "./client";

export async function listWorkflows(): Promise<Workflow[]> {
  const { data } = await apiClient.get<Workflow[]>("/workflows");
  return data;
}

export async function getWorkflow(id: number): Promise<Workflow> {
  const { data } = await apiClient.get<Workflow>(`/workflows/${id}`);
  return data;
}

export async function createWorkflow(payload: WorkflowCreatePayload): Promise<Workflow> {
  const { data } = await apiClient.post<Workflow>("/workflows", payload);
  return data;
}

export async function updateWorkflow(
  id: number,
  payload: WorkflowUpdatePayload,
): Promise<Workflow> {
  const { data } = await apiClient.patch<Workflow>(`/workflows/${id}`, payload);
  return data;
}

export async function deleteWorkflow(id: number): Promise<void> {
  await apiClient.delete(`/workflows/${id}`);
}

export async function runWorkflow(id: number, input?: Record<string, unknown>): Promise<Execution> {
  const { data } = await apiClient.post<Execution>(`/workflows/${id}/run`, {
    input_data: input ?? {},
  });
  return data;
}
