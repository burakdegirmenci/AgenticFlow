import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { FlowEdge, FlowNode } from "@/types/workflow";

import { useWorkflowStore } from "../workflowStore";

const makeNode = (id: string, type = "transform.filter"): FlowNode => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data: { label: `Node ${id}`, config: {} },
});

const makeEdge = (source: string, target: string): FlowEdge => ({
  id: `${source}-${target}`,
  source,
  target,
});

describe("useWorkflowStore", () => {
  beforeEach(() => {
    act(() => {
      useWorkflowStore.getState().reset();
    });
  });

  it("has sensible initial state", () => {
    const state = useWorkflowStore.getState();
    expect(state.workflowId).toBeNull();
    expect(state.name).toBe("");
    expect(state.siteId).toBeNull();
    expect(state.nodes).toEqual([]);
    expect(state.edges).toEqual([]);
    expect(state.selectedNodeId).toBeNull();
    expect(state.dirty).toBe(false);
  });

  it("loadWorkflow hydrates the store and clears dirty flag", () => {
    act(() => {
      useWorkflowStore.getState().loadWorkflow({
        id: 7,
        name: "Daily Orders",
        siteId: 3,
        graph: {
          nodes: [makeNode("n1"), makeNode("n2")],
          edges: [makeEdge("n1", "n2")],
        },
      });
    });

    const state = useWorkflowStore.getState();
    expect(state.workflowId).toBe(7);
    expect(state.name).toBe("Daily Orders");
    expect(state.siteId).toBe(3);
    expect(state.nodes).toHaveLength(2);
    expect(state.edges).toHaveLength(1);
    expect(state.dirty).toBe(false);
  });

  it("every mutating setter flips dirty to true", () => {
    const store = useWorkflowStore.getState();

    act(() => {
      store.setName("edited");
    });
    expect(useWorkflowStore.getState().dirty).toBe(true);

    act(() => {
      useWorkflowStore.getState().markClean();
      useWorkflowStore.getState().setSiteId(9);
    });
    expect(useWorkflowStore.getState().dirty).toBe(true);
  });

  it("addNode appends without touching existing nodes", () => {
    act(() => {
      useWorkflowStore.getState().setNodes([makeNode("a")]);
    });
    act(() => {
      useWorkflowStore.getState().addNode(makeNode("b"));
    });

    const ids = useWorkflowStore.getState().nodes.map((n) => n.id);
    expect(ids).toEqual(["a", "b"]);
  });

  it("updateNodeConfig merges into existing config", () => {
    act(() => {
      const n = makeNode("n1");
      n.data = { ...n.data, config: { limit: 10, active: true } };
      useWorkflowStore.getState().setNodes([n]);
    });

    act(() => {
      useWorkflowStore.getState().updateNodeConfig("n1", { limit: 25 });
    });

    const [node] = useWorkflowStore.getState().nodes;
    expect(node?.data.config).toEqual({ limit: 25, active: true });
  });

  it("removeNode drops the node and all edges referencing it", () => {
    act(() => {
      useWorkflowStore.getState().setNodes([makeNode("a"), makeNode("b"), makeNode("c")]);
      useWorkflowStore.getState().setEdges([makeEdge("a", "b"), makeEdge("b", "c")]);
      useWorkflowStore.getState().setSelectedNode("b");
    });

    act(() => {
      useWorkflowStore.getState().removeNode("b");
    });

    const state = useWorkflowStore.getState();
    expect(state.nodes.map((n) => n.id)).toEqual(["a", "c"]);
    expect(state.edges).toEqual([]);
    expect(state.selectedNodeId).toBeNull();
  });

  it("removeNode keeps selection when unrelated node is removed", () => {
    act(() => {
      useWorkflowStore.getState().setNodes([makeNode("a"), makeNode("b")]);
      useWorkflowStore.getState().setSelectedNode("b");
    });

    act(() => {
      useWorkflowStore.getState().removeNode("a");
    });

    expect(useWorkflowStore.getState().selectedNodeId).toBe("b");
  });

  it("reset restores initial state", () => {
    act(() => {
      useWorkflowStore.getState().loadWorkflow({
        id: 1,
        name: "x",
        siteId: 1,
        graph: { nodes: [makeNode("a")], edges: [] },
      });
    });

    act(() => {
      useWorkflowStore.getState().reset();
    });

    const state = useWorkflowStore.getState();
    expect(state.workflowId).toBeNull();
    expect(state.nodes).toEqual([]);
    expect(state.dirty).toBe(false);
  });
});
