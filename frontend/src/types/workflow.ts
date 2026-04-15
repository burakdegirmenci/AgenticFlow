export interface FlowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label?: string;
    config?: Record<string, unknown>;
    [key: string]: unknown;
  };
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  label?: string;
}

export interface WorkflowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface Workflow {
  id: number;
  name: string;
  description: string | null;
  site_id: number;
  graph_json: WorkflowGraph;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreatePayload {
  name: string;
  description?: string | null;
  site_id: number;
  graph_json?: WorkflowGraph;
  is_active?: boolean;
}

export interface WorkflowUpdatePayload {
  name?: string;
  description?: string | null;
  graph_json?: WorkflowGraph;
  is_active?: boolean;
}
