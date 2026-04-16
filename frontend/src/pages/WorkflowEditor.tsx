import "@xyflow/react/dist/style.css";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addEdge,
  Background,
  type Connection,
  Controls,
  type Edge as RFEdge,
  type EdgeChange,
  MiniMap,
  type Node as RFNode,
  type NodeChange,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import { ArrowLeft, MessageCircle, Play, Power, Save } from "lucide-react";
import { type DragEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { WorkflowProposal } from "@/api/agent";
import { getExecution } from "@/api/executions";
import { listNodes } from "@/api/nodes";
import { getWorkflow, runWorkflow, updateWorkflow } from "@/api/workflows";
import { CustomNode } from "@/components/Canvas/CustomNode";
import NodeConfigPanel from "@/components/Canvas/NodeConfigPanel";
import NodePalette, { NODE_DRAG_MIME } from "@/components/Canvas/NodePalette";
import { NodeRenderProvider } from "@/components/Canvas/NodeRenderContext";
import AgentChat from "@/components/Chat/AgentChat";
import RunWorkflowDialog from "@/components/RunWorkflowDialog";
import { useChatStore } from "@/store/chatStore";
import type { ExecutionDetail } from "@/types/execution";

/**
 * Wrapper that lets the user drop a palette node onto the canvas. Lives
 * inside `ReactFlowProvider` so it can use `useReactFlow().screenToFlowPosition`
 * to convert the drop coordinates into the canvas's own coordinate system,
 * which respects the current zoom and pan.
 */
function FlowDropZone({
  onDropNode,
  children,
}: {
  onDropNode: (typeId: string, position: { x: number; y: number }) => void;
  children: ReactNode;
}) {
  const { screenToFlowPosition } = useReactFlow();

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (event.dataTransfer.types.includes(NODE_DRAG_MIME)) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    const typeId = event.dataTransfer.getData(NODE_DRAG_MIME);
    if (!typeId) return;
    event.preventDefault();
    const position = screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    onDropNode(typeId, position);
  };

  return (
    <div className="h-full w-full" onDragOver={handleDragOver} onDrop={handleDrop}>
      {children}
    </div>
  );
}

export default function WorkflowEditor() {
  const { id } = useParams<{ id: string }>();
  const workflowId = Number(id);
  const qc = useQueryClient();

  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [activeExecutionId, setActiveExecutionId] = useState<number | null>(null);
  const chatOpen = useChatStore((s) => s.open);
  const toggleChat = useChatStore((s) => s.toggle);
  const setChatOpen = useChatStore((s) => s.setOpen);

  const workflow = useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => getWorkflow(workflowId),
    enabled: Number.isFinite(workflowId),
  });

  const catalog = useQuery({ queryKey: ["nodes"], queryFn: listNodes });

  useEffect(() => {
    if (workflow.data) {
      const graph = workflow.data.graph_json ?? { nodes: [], edges: [] };
      setNodes((graph.nodes ?? []) as RFNode[]);
      setEdges((graph.edges ?? []) as RFEdge[]);
      setDirty(false);
    }
  }, [workflow.data, setNodes, setEdges]);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );
  const selectedCatalog = useMemo(() => {
    if (!selectedNode || !catalog.data) return null;
    return catalog.data.find((c) => c.type_id === (selectedNode.type as string)) ?? null;
  }, [selectedNode, catalog.data]);

  const handleConnect = (connection: Connection) => {
    setEdges((eds) => addEdge({ ...connection }, eds));
    setDirty(true);
  };

  const handleNodesChange = (changes: NodeChange[]) => {
    onNodesChange(changes);
    if (changes.some((c) => c.type !== "select" && c.type !== "dimensions")) setDirty(true);
  };

  const handleEdgesChange = (changes: EdgeChange[]) => {
    onEdgesChange(changes);
    if (changes.some((c) => c.type !== "select")) setDirty(true);
  };

  const addNodeAtPosition = (typeId: string, position: { x: number; y: number }) => {
    const catalogEntry = catalog.data?.find((c) => c.type_id === typeId);
    if (!catalogEntry) return;
    const newNode: RFNode = {
      id: `n_${Date.now()}`,
      type: typeId,
      position,
      data: {
        label: catalogEntry.display_name,
        config: {},
      },
    };
    setNodes((nds) => [...nds, newNode]);
    setDirty(true);
  };

  const addNodeFromPalette = (typeId: string) => {
    addNodeAtPosition(typeId, {
      x: 200 + Math.random() * 200,
      y: 100 + Math.random() * 200,
    });
  };

  const handleApplyProposal = (proposal: WorkflowProposal) => {
    // Convert proposal nodes/edges into React Flow shape and place onto canvas.
    // We append rather than replace, so the user can iterate. Existing nodes
    // are kept; new nodes get a unique id prefix to avoid collisions.
    const idPrefix = `ag_${Date.now().toString(36)}_`;
    const idMap = new Map<string, string>();

    const incomingNodes: RFNode[] = proposal.nodes.map((n, i) => {
      const newId = `${idPrefix}${n.id}`;
      idMap.set(n.id, newId);
      return {
        id: newId,
        type: n.type,
        position: n.position ?? { x: 200 + i * 220, y: 140 },
        data: {
          label: n.data?.label ?? n.type,
          config: n.data?.config ?? {},
        },
      };
    });

    const incomingEdges: RFEdge[] = proposal.edges
      .map((e, i) => {
        const src = idMap.get(e.source);
        const tgt = idMap.get(e.target);
        if (!src || !tgt) return null;
        return {
          id: `${idPrefix}e${i}`,
          source: src,
          target: tgt,
          sourceHandle: e.sourceHandle ?? null,
          targetHandle: e.targetHandle ?? null,
        } as RFEdge;
      })
      .filter((e): e is RFEdge => e !== null);

    setNodes((nds) => [...nds, ...incomingNodes]);
    setEdges((eds) => [...eds, ...incomingEdges]);
    setDirty(true);
  };

  const deleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNodeId === nodeId) setSelectedNodeId(null);
    setDirty(true);
  };

  const updateSelectedNodeConfig = (config: Record<string, unknown>) => {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNodeId
          ? {
              ...n,
              data: {
                ...n.data,
                config: { ...(n.data.config as object | undefined), ...config },
              },
            }
          : n,
      ),
    );
    setDirty(true);
  };

  const saveMut = useMutation({
    mutationFn: () =>
      updateWorkflow(workflowId, {
        graph_json: {
          nodes: nodes.map((n) => ({
            id: n.id,
            type: n.type ?? "unknown",
            position: n.position,
            data: n.data,
          })),
          edges: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: e.sourceHandle ?? null,
            targetHandle: e.targetHandle ?? null,
          })),
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflow", workflowId] });
      qc.invalidateQueries({ queryKey: ["workflows"] });
      setDirty(false);
    },
  });

  const [showRunDialog, setShowRunDialog] = useState(false);

  const runMut = useMutation({
    mutationFn: (inputData?: Record<string, unknown>) => runWorkflow(workflowId, inputData),
    onSuccess: (execution) => {
      setShowRunDialog(false);
      setActiveExecutionId(execution.id);
      qc.invalidateQueries({ queryKey: ["executions"] });
    },
  });

  // Activate/deactivate toggle — hits PATCH /workflows/:id with {is_active}.
  // Backend wires this into SchedulerService so cron/polling jobs get
  // registered/unregistered in one round-trip.
  const activateMut = useMutation({
    mutationFn: (next: boolean) => updateWorkflow(workflowId, { is_active: next }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflow", workflowId] });
      qc.invalidateQueries({ queryKey: ["workflows"] });
    },
  });

  // Live polling: while an execution is PENDING/RUNNING, refetch every 600ms
  // so the canvas can show per-node status (CustomNode reads from this).
  const liveExecution = useQuery<ExecutionDetail>({
    queryKey: ["execution", activeExecutionId],
    queryFn: () => getExecution(activeExecutionId as number),
    enabled: activeExecutionId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "PENDING" || status === "RUNNING") return 600;
      return false;
    },
  });

  // When the live execution finishes, refresh the executions list once.
  useEffect(() => {
    const status = liveExecution.data?.status;
    if (status === "SUCCESS" || status === "ERROR" || status === "CANCELLED") {
      qc.invalidateQueries({ queryKey: ["executions"] });
    }
  }, [liveExecution.data?.status, qc]);

  // True from the moment Run is clicked until the live execution reports a
  // terminal status. Three conditions cover the full lifecycle:
  //   1. Mutation is in flight (runMut.isPending)
  //   2. Live execution has been queried and is PENDING/RUNNING
  //   3. We just dispatched an execution but the first poll hasn't returned
  //      yet (activeExecutionId is set, liveExecution.data is undefined)
  const liveStatus = liveExecution.data?.status;
  const liveIsTerminal =
    liveStatus === "SUCCESS" || liveStatus === "ERROR" || liveStatus === "CANCELLED";
  const isRunning = runMut.isPending || (activeExecutionId !== null && !liveIsTerminal);

  // Build the React Flow nodeTypes map: every catalog entry renders through
  // CustomNode. Computed once per catalog refresh so React Flow doesn't warn
  // about unstable references on re-render.
  const nodeTypes = useMemo(() => {
    const map: Record<string, typeof CustomNode> = {};
    if (catalog.data) {
      for (const entry of catalog.data) map[entry.type_id] = CustomNode;
    }
    return map;
  }, [catalog.data]);

  // Decorate edges with live execution state: animate edges feeding into a
  // currently-RUNNING node and color them based on the surrounding step
  // statuses (success → emerald, error → red, idle → default).
  const displayEdges = useMemo<RFEdge[]>(() => {
    const steps = liveExecution.data?.steps ?? [];
    if (steps.length === 0) return edges;
    const stepByNode = new Map(steps.map((s) => [s.node_id, s]));

    return edges.map((edge) => {
      const sourceStep = stepByNode.get(edge.source);
      const targetStep = stepByNode.get(edge.target);

      let stroke = "#9ca3af"; // default neutral-400
      let animated = false;

      if (targetStep?.status === "RUNNING") {
        stroke = "#2563eb"; // accent
        animated = true;
      } else if (sourceStep?.status === "ERROR" || targetStep?.status === "ERROR") {
        stroke = "#dc2626"; // red-600
      } else if (sourceStep?.status === "SUCCESS" && targetStep?.status === "SUCCESS") {
        stroke = "#16a34a"; // emerald-600
      } else if (sourceStep?.status === "SUCCESS" && !targetStep) {
        // Source produced output but target hasn't started yet
        stroke = "#16a34a";
      }

      return {
        ...edge,
        animated,
        style: { ...(edge.style ?? {}), stroke, strokeWidth: 2 },
      };
    });
  }, [edges, liveExecution.data]);

  if (workflow.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-neutral-500">
        Yükleniyor…
      </div>
    );
  }

  if (!workflow.data) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-neutral-500">
        Workflow bulunamadı.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-4">
        <div className="flex items-center gap-3">
          <Link
            to="/workflows"
            className="flex items-center gap-1 text-[12px] text-neutral-600 hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
            Geri
          </Link>
          <div className="h-4 w-px bg-neutral-200" />
          <h1 className="text-[14px] font-semibold">{workflow.data.name}</h1>
          {workflow.data.is_active ? (
            <span
              className="border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-700"
              title="Scheduler aktif"
            >
              Aktif
            </span>
          ) : (
            <span className="border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-neutral-500">
              Pasif
            </span>
          )}
          {dirty && (
            <span className="border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-700">
              Kaydedilmedi
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => activateMut.mutate(!workflow.data?.is_active)}
            disabled={activateMut.isPending || dirty}
            className={[
              "flex items-center gap-1 border px-3 py-1.5 text-[12px] font-medium disabled:opacity-40",
              workflow.data?.is_active
                ? "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50",
            ].join(" ")}
            title={
              dirty
                ? "Önce kaydet"
                : workflow.data?.is_active
                  ? "Scheduler'ı durdur"
                  : "Scheduler'ı başlat (cron/polling jobs)"
            }
          >
            <Power className="h-3.5 w-3.5" strokeWidth={2} />
            {activateMut.isPending ? "…" : workflow.data?.is_active ? "Aktif" : "Pasif"}
          </button>
          <button
            onClick={toggleChat}
            className={[
              "flex items-center gap-1 border px-3 py-1.5 text-[12px] font-medium",
              chatOpen
                ? "border-accent bg-accent text-white hover:bg-accent-hover"
                : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50",
            ].join(" ")}
            title="Agent Chat"
          >
            <MessageCircle className="h-3.5 w-3.5" strokeWidth={2} />
            Agent
          </button>
          <button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending || !dirty}
            className="flex items-center gap-1 border border-neutral-300 bg-white px-3 py-1.5 text-[12px] font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40"
          >
            <Save className="h-3.5 w-3.5" strokeWidth={2} />
            {saveMut.isPending ? "Kaydediliyor…" : "Kaydet"}
          </button>
          <button
            onClick={() => {
              const schema = workflow.data?.input_schema;
              if (schema && typeof schema === "object" && Object.keys(schema.properties ?? {}).length > 0) {
                setShowRunDialog(true);
              } else {
                runMut.mutate(undefined);
              }
            }}
            disabled={isRunning || dirty}
            className="flex items-center gap-1 border border-accent bg-accent px-3 py-1.5 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-40"
            title={dirty ? "Önce kaydet" : "Çalıştır"}
          >
            <Play className="h-3.5 w-3.5" strokeWidth={2} />
            {isRunning ? "Çalıştırılıyor…" : "Run"}
          </button>
        </div>
      </header>

      {/* Runtime input dialog — shown when workflow has input_schema */}
      {showRunDialog && workflow.data?.input_schema && (
        <RunWorkflowDialog
          workflowId={workflowId}
          inputSchema={workflow.data.input_schema as unknown as Parameters<typeof RunWorkflowDialog>[0]["inputSchema"]}
          onClose={() => setShowRunDialog(false)}
          onRun={(inputData) => runMut.mutate(inputData)}
          isRunning={runMut.isPending}
        />
      )}

      <div className="flex flex-1 overflow-hidden">
        <NodePalette catalog={catalog.data ?? []} onAdd={addNodeFromPalette} />
        <div className="relative flex-1 bg-neutral-50">
          <NodeRenderProvider
            catalog={catalog.data}
            liveExecution={liveExecution.data}
            isRunning={isRunning}
          >
            <ReactFlowProvider>
              <FlowDropZone onDropNode={addNodeAtPosition}>
                <ReactFlow
                  nodes={nodes}
                  edges={displayEdges}
                  nodeTypes={nodeTypes}
                  onNodesChange={handleNodesChange}
                  onEdgesChange={handleEdgesChange}
                  onConnect={handleConnect}
                  onNodeClick={(_, n) => setSelectedNodeId(n.id)}
                  onPaneClick={() => setSelectedNodeId(null)}
                  onNodesDelete={(deleted) => {
                    if (deleted.some((n) => n.id === selectedNodeId)) setSelectedNodeId(null);
                    setDirty(true);
                  }}
                  deleteKeyCode={["Delete", "Backspace"]}
                  fitView
                  proOptions={{ hideAttribution: true }}
                >
                  <Background gap={16} size={1} color="#e5e5e5" />
                  <Controls showInteractive={false} />
                  <MiniMap pannable zoomable />
                </ReactFlow>
              </FlowDropZone>
            </ReactFlowProvider>
          </NodeRenderProvider>
        </div>
        <NodeConfigPanel
          node={selectedNode}
          catalog={selectedCatalog}
          onUpdate={updateSelectedNodeConfig}
          onDelete={deleteNode}
        />
        {chatOpen && (
          <AgentChat
            workflowId={workflowId}
            onApplyProposal={handleApplyProposal}
            onClose={() => setChatOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
