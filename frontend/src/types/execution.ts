export type ExecutionStatus = "PENDING" | "RUNNING" | "SUCCESS" | "ERROR" | "CANCELLED" | "SKIPPED";

export type TriggerType = "MANUAL" | "SCHEDULE" | "POLLING" | "AGENT";

export interface ExecutionStep {
  id: number;
  execution_id: number;
  node_id: string;
  node_type: string;
  status: ExecutionStatus;
  started_at: string;
  finished_at: string | null;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error: string | null;
  duration_ms: number | null;
}

export interface Execution {
  id: number;
  workflow_id: number;
  status: ExecutionStatus;
  trigger_type: TriggerType;
  started_at: string;
  finished_at: string | null;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error: string | null;
}

export interface ExecutionDetail extends Execution {
  steps: ExecutionStep[];
}
