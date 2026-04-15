import { create } from "zustand";

import type { FlowEdge, FlowNode, WorkflowGraph } from "@/types/workflow";

interface WorkflowState {
  workflowId: number | null;
  name: string;
  siteId: number | null;
  nodes: FlowNode[];
  edges: FlowEdge[];
  selectedNodeId: string | null;
  dirty: boolean;

  loadWorkflow: (payload: {
    id: number;
    name: string;
    siteId: number;
    graph: WorkflowGraph;
  }) => void;
  reset: () => void;
  setName: (name: string) => void;
  setSiteId: (siteId: number) => void;
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: FlowEdge[]) => void;
  addNode: (node: FlowNode) => void;
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void;
  removeNode: (nodeId: string) => void;
  setSelectedNode: (nodeId: string | null) => void;
  markClean: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  workflowId: null,
  name: "",
  siteId: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  dirty: false,

  loadWorkflow: ({ id, name, siteId, graph }) =>
    set({
      workflowId: id,
      name,
      siteId,
      nodes: graph.nodes ?? [],
      edges: graph.edges ?? [],
      selectedNodeId: null,
      dirty: false,
    }),

  reset: () =>
    set({
      workflowId: null,
      name: "",
      siteId: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      dirty: false,
    }),

  setName: (name) => set({ name, dirty: true }),
  setSiteId: (siteId) => set({ siteId, dirty: true }),
  setNodes: (nodes) => set({ nodes, dirty: true }),
  setEdges: (edges) => set({ edges, dirty: true }),
  addNode: (node) => set((state) => ({ nodes: [...state.nodes, node], dirty: true })),
  updateNodeConfig: (nodeId, config) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, config: { ...n.data.config, ...config } } }
          : n,
      ),
      dirty: true,
    })),
  removeNode: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
      dirty: true,
    })),
  setSelectedNode: (nodeId) => set({ selectedNodeId: nodeId }),
  markClean: () => set({ dirty: false }),
}));
