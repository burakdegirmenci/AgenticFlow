import { createContext, type ReactNode, useContext, useMemo } from "react";

import type { ExecutionDetail, ExecutionStep } from "@/types/execution";
import type { NodeCatalogEntry } from "@/types/node";

export interface NodeRenderContextValue {
  /** Look up a catalog entry by node type id (e.g. `ticimax.urun.select`). */
  getCatalog: (typeId: string | undefined | null) => NodeCatalogEntry | null;
  /** Look up the latest execution step for a given graph node id. */
  getLiveStep: (nodeId: string) => ExecutionStep | null;
  /** True while an execution is actively running on this workflow. */
  isRunning: boolean;
}

const NoopContext: NodeRenderContextValue = {
  getCatalog: () => null,
  getLiveStep: () => null,
  isRunning: false,
};

const NodeRenderContext = createContext<NodeRenderContextValue>(NoopContext);

interface ProviderProps {
  catalog: NodeCatalogEntry[] | undefined;
  liveExecution: ExecutionDetail | undefined;
  isRunning: boolean;
  children: ReactNode;
}

export function NodeRenderProvider({ catalog, liveExecution, isRunning, children }: ProviderProps) {
  const value = useMemo<NodeRenderContextValue>(() => {
    const catalogIndex = new Map<string, NodeCatalogEntry>();
    if (catalog) {
      for (const entry of catalog) catalogIndex.set(entry.type_id, entry);
    }

    // Index live steps by node_id; if there are duplicates (which shouldn't
    // happen for a single execution) the latest one wins.
    const stepIndex = new Map<string, ExecutionStep>();
    if (liveExecution?.steps) {
      for (const step of liveExecution.steps) stepIndex.set(step.node_id, step);
    }

    return {
      getCatalog: (typeId) => (typeId && catalogIndex.get(typeId)) || null,
      getLiveStep: (nodeId) => stepIndex.get(nodeId) ?? null,
      isRunning,
    };
  }, [catalog, liveExecution, isRunning]);

  return <NodeRenderContext.Provider value={value}>{children}</NodeRenderContext.Provider>;
}

export function useNodeRender(): NodeRenderContextValue {
  return useContext(NodeRenderContext);
}
