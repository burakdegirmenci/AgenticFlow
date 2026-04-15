import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import { memo, useMemo } from "react";

import { getNodeIcon } from "./iconMap";
import { useNodeRender } from "./NodeRenderContext";

interface CustomNodeData {
  label?: string;
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

type CustomNodeType = Node<CustomNodeData>;

/**
 * Visual node renderer used for every workflow node on the canvas.
 *
 * Layout:
 *   ┌─────────────────────────────────┐
 *   │ ▌ [icon]  Display Name      [●] │  ← header (category stripe + status dot)
 *   │ ▌  type.id.here                 │
 *   │ ▌ ─────────────────────────────  │
 *   │ ▌  config preview / placeholder │  ← body
 *   │ ▌                          [⚠]  │
 *   └─────────────────────────────────┘
 *      ▲ top handle             ▼ bottom handle
 */
function CustomNodeImpl({ id, type, data, selected }: NodeProps<CustomNodeType>) {
  const { getCatalog, getLiveStep, isRunning } = useNodeRender();

  const typeId = type ?? "";
  const catalog = getCatalog(typeId);
  const step = getLiveStep(id);

  const Icon = getNodeIcon(catalog?.icon);
  const accent = catalog?.color || "#6b7280";
  const displayName = data?.label || catalog?.display_name || typeId || "Node";

  // Live status takes precedence over the static "idle" state.
  const status = step?.status;

  // Validation: any required config field that is empty?
  const missingRequired = useMemo(() => {
    if (!catalog) return [] as string[];
    const schema = catalog.config_schema as
      | { properties?: Record<string, { type?: string }>; required?: string[] }
      | undefined;
    const required = schema?.required ?? [];
    if (required.length === 0) return [] as string[];
    const config = data?.config ?? {};
    return required.filter((key) => {
      const v = config[key];
      if (v === undefined || v === null) return true;
      if (typeof v === "string" && v.trim() === "") return true;
      return false;
    });
  }, [catalog, data?.config]);

  // Compact one-line config preview
  const configPreview = useMemo(() => {
    const config = data?.config ?? {};
    const entries = Object.entries(config).filter(
      ([, v]) => v !== "" && v !== null && v !== undefined,
    );
    if (entries.length === 0) return null;
    const [k, v] = entries[0];
    let valueText: string;
    if (typeof v === "string") valueText = v;
    else if (typeof v === "number" || typeof v === "boolean") valueText = String(v);
    else valueText = JSON.stringify(v);
    if (valueText.length > 28) valueText = valueText.slice(0, 27) + "…";
    return `${k}: ${valueText}`;
  }, [data?.config]);

  // Tooltip output preview (best-effort short JSON)
  const outputPreview = useMemo(() => {
    if (!step?.output_data) return null;
    try {
      const json = JSON.stringify(step.output_data);
      if (json.length <= 240) return json;
      return json.slice(0, 237) + "…";
    } catch {
      return null;
    }
  }, [step?.output_data]);

  // Status indicator (top-right of header)
  const StatusBadge = () => {
    if (status === "RUNNING") {
      return (
        <Loader2
          className="h-3.5 w-3.5 animate-spin text-accent"
          strokeWidth={2.5}
          aria-label="Running"
        />
      );
    }
    if (status === "SUCCESS") {
      return (
        <CheckCircle2
          className="h-3.5 w-3.5 text-emerald-600"
          strokeWidth={2.5}
          aria-label="Success"
        />
      );
    }
    if (status === "ERROR") {
      return <XCircle className="h-3.5 w-3.5 text-red-600" strokeWidth={2.5} aria-label="Error" />;
    }
    if (status === "PENDING") {
      return (
        <CircleDashed
          className="h-3.5 w-3.5 text-neutral-400"
          strokeWidth={2.5}
          aria-label="Pending"
        />
      );
    }
    // Idle: dim dot of category color
    return (
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: accent }}
        aria-hidden
      />
    );
  };

  const isErrorState = status === "ERROR";
  const isRunningState = status === "RUNNING";
  const showRunningGlow = isRunning && isRunningState;

  // Nodes that fan out along named branches need explicit Handle ids so
  // React Flow can resolve edges that use `sourceHandle: "true" | "false"
  // | <case>"`. For everything else we render a single default bottom handle.
  const isIfNode = typeId === "logic.if";
  const isSwitchNode = typeId === "logic.switch";
  const branchHandles: { id: string; label: string }[] = isIfNode
    ? [
        { id: "true", label: "TRUE" },
        { id: "false", label: "FALSE" },
      ]
    : [];

  // Border colors layered: error > running > selected > idle
  let borderClass = "border-neutral-300";
  if (isErrorState) borderClass = "border-red-500";
  else if (showRunningGlow) borderClass = "border-accent";
  else if (selected) borderClass = "border-ink";

  return (
    <div
      className={[
        "group relative flex w-[220px] flex-col bg-white text-[12px] text-neutral-800",
        "border shadow-sm transition-shadow",
        borderClass,
        showRunningGlow ? "shadow-[0_0_0_2px_rgba(37,99,235,0.18)]" : "",
        selected && !showRunningGlow && !isErrorState
          ? "shadow-[0_0_0_2px_rgba(10,10,10,0.08)]"
          : "",
      ].join(" ")}
    >
      {/* Top handle (target) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-2 !border-white !bg-neutral-400"
      />

      {/* Header row */}
      <div className="flex items-stretch">
        {/* Category color stripe */}
        <div className="w-1 shrink-0" style={{ backgroundColor: accent }} aria-hidden />
        <div className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-2">
          <div
            className="flex h-6 w-6 shrink-0 items-center justify-center"
            style={{ backgroundColor: `${accent}15` }}
          >
            <Icon className="h-3.5 w-3.5" strokeWidth={2} style={{ color: accent }} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[12px] font-semibold leading-tight text-ink">
              {displayName}
            </div>
            <div className="truncate text-[9px] uppercase tracking-wider text-neutral-400">
              {typeId}
            </div>
          </div>
          <StatusBadge />
        </div>
      </div>

      {/* Body */}
      <div className="flex items-stretch border-t border-neutral-100">
        <div className="w-1 shrink-0" aria-hidden />
        <div className="flex min-w-0 flex-1 items-center justify-between gap-2 px-2.5 py-1.5">
          <div className="min-w-0 flex-1 truncate text-[10.5px] text-neutral-500">
            {configPreview ?? <span className="italic text-neutral-300">— config —</span>}
          </div>
          {missingRequired.length > 0 && (
            <span
              title={`Eksik alan: ${missingRequired.join(", ")}`}
              className="flex shrink-0 items-center gap-0.5 border border-amber-300 bg-amber-50 px-1 py-px text-[9px] font-medium uppercase tracking-wider text-amber-700"
            >
              <AlertTriangle className="h-2.5 w-2.5" strokeWidth={2.5} />
              {missingRequired.length}
            </span>
          )}
        </div>
      </div>

      {/* Duration footer (only when we have a finished step) */}
      {step?.duration_ms != null && status !== "RUNNING" && (
        <div className="flex items-stretch border-t border-neutral-100">
          <div className="w-1 shrink-0" aria-hidden />
          <div className="px-2.5 py-1 text-[9.5px] text-neutral-400">{step.duration_ms} ms</div>
        </div>
      )}

      {/* Bottom handle(s) (source) */}
      {branchHandles.length > 0 ? (
        <>
          {branchHandles.map((h, i) => {
            // Evenly distribute handles along the bottom edge.
            const left = `${((i + 1) * 100) / (branchHandles.length + 1)}%`;
            const isTrue = h.id === "true";
            return (
              <Handle
                key={h.id}
                id={h.id}
                type="source"
                position={Position.Bottom}
                style={{ left }}
                className={[
                  "!h-2.5 !w-2.5 !border-2 !border-white",
                  isTrue ? "!bg-emerald-500" : "!bg-red-500",
                ].join(" ")}
                title={h.label}
              />
            );
          })}
          {/* Branch labels above the handles so users can tell them apart */}
          <div className="pointer-events-none absolute inset-x-0 bottom-[-14px] flex justify-around px-4">
            {branchHandles.map((h) => (
              <span
                key={h.id}
                className={[
                  "text-[8px] font-semibold uppercase tracking-wider",
                  h.id === "true" ? "text-emerald-600" : "text-red-600",
                ].join(" ")}
              >
                {h.label}
              </span>
            ))}
          </div>
        </>
      ) : (
        <Handle
          type="source"
          position={Position.Bottom}
          className="!h-2 !w-2 !border-2 !border-white !bg-neutral-400"
        />
      )}
      {/* Unused flag to keep the lint happy when switch support lands later */}
      {isSwitchNode ? null : null}

      {/* Hover summary tooltip — appears on the right of the node */}
      <div className="pointer-events-none absolute left-[calc(100%+8px)] top-0 z-50 hidden w-[280px] border border-neutral-200 bg-white shadow-lg group-hover:block">
        <div className="border-b border-neutral-100 px-3 py-2">
          <div className="text-[12px] font-semibold text-ink">{displayName}</div>
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">{typeId}</div>
        </div>
        {catalog?.description && (
          <div className="border-b border-neutral-100 px-3 py-2 text-[11px] leading-snug text-neutral-600">
            {catalog.description}
          </div>
        )}
        {step ? (
          <div className="px-3 py-2 text-[11px] text-neutral-600">
            <div className="flex items-center justify-between">
              <span className="font-medium text-ink">Son çalıştırma</span>
              <span
                className={[
                  "text-[10px] font-semibold uppercase tracking-wider",
                  step.status === "SUCCESS" && "text-emerald-600",
                  step.status === "ERROR" && "text-red-600",
                  step.status === "RUNNING" && "text-accent",
                  step.status === "PENDING" && "text-neutral-400",
                  step.status === "SKIPPED" && "text-neutral-400",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {step.status}
              </span>
            </div>
            {step.duration_ms != null && (
              <div className="mt-0.5 text-[10px] text-neutral-400">Süre: {step.duration_ms} ms</div>
            )}
            {step.error && (
              <div className="mt-1 max-h-20 overflow-hidden whitespace-pre-wrap break-words border-l-2 border-red-300 pl-2 text-[10px] text-red-600">
                {step.error}
              </div>
            )}
            {outputPreview && !step.error && (
              <div className="mt-1 max-h-24 overflow-hidden break-all font-mono text-[10px] text-neutral-500">
                {outputPreview}
              </div>
            )}
          </div>
        ) : (
          <div className="px-3 py-2 text-[11px] italic text-neutral-400">Henüz çalıştırılmadı</div>
        )}
      </div>
    </div>
  );
}

export const CustomNode = memo(CustomNodeImpl);
