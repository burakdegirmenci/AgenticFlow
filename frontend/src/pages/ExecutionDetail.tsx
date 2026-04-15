import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getExecution } from "@/api/executions";
import type { ExecutionStep } from "@/types/execution";

export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const executionId = Number(id);

  const exec = useQuery({
    queryKey: ["execution", executionId],
    queryFn: () => getExecution(executionId),
    enabled: Number.isFinite(executionId),
    refetchInterval: (query) => (query.state.data?.status === "RUNNING" ? 2_000 : false),
  });

  if (exec.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-neutral-500">
        Yükleniyor…
      </div>
    );
  }

  if (!exec.data) {
    return (
      <div className="flex h-full items-center justify-center text-[13px] text-neutral-500">
        Execution bulunamadı.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <header className="flex h-14 items-center justify-between border-b border-neutral-200 px-6">
        <div className="flex items-center gap-3">
          <Link
            to="/executions"
            className="flex items-center gap-1 text-[12px] text-neutral-600 hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
            Geri
          </Link>
          <div className="h-4 w-px bg-neutral-200" />
          <h1 className="text-[15px] font-semibold tracking-tight">Execution #{exec.data.id}</h1>
          <StatusBadge status={exec.data.status} />
        </div>
      </header>

      <div className="p-6">
        <div className="mb-6 grid grid-cols-4 gap-4">
          <InfoCell label="Workflow" value={`#${exec.data.workflow_id}`} />
          <InfoCell label="Trigger" value={exec.data.trigger_type} />
          <InfoCell
            label="Başlangıç"
            value={new Date(exec.data.started_at).toLocaleString("tr-TR")}
          />
          <InfoCell
            label="Bitiş"
            value={
              exec.data.finished_at ? new Date(exec.data.finished_at).toLocaleString("tr-TR") : "—"
            }
          />
        </div>

        {exec.data.error && (
          <div className="mb-6 whitespace-pre-wrap border border-red-200 bg-red-50 p-3 font-mono text-[12px] text-red-700">
            {exec.data.error}
          </div>
        )}

        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-neutral-600">
          Adımlar
        </h2>
        <div className="space-y-2">
          {exec.data.steps.length === 0 ? (
            <div className="border border-neutral-200 bg-white p-4 text-[13px] text-neutral-500">
              Adım yok.
            </div>
          ) : (
            exec.data.steps.map((step) => <StepRow key={step.id} step={step} />)
          )}
        </div>
      </div>
    </div>
  );
}

function StepRow({ step }: { step: ExecutionStep }) {
  return (
    <details className="border border-neutral-200 bg-white">
      <summary className="flex cursor-pointer items-center justify-between px-4 py-2.5 text-[13px] hover:bg-neutral-50">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-neutral-500">{step.node_id}</span>
          <span className="font-medium">{step.node_type}</span>
          <StatusBadge status={step.status} />
        </div>
        <span className="font-mono text-[11px] text-neutral-500">
          {step.duration_ms !== null ? `${step.duration_ms} ms` : "—"}
        </span>
      </summary>
      <div className="border-t border-neutral-100 px-4 py-3 text-[12px]">
        {step.error && (
          <div className="mb-3 whitespace-pre-wrap border border-red-200 bg-red-50 p-2 font-mono text-red-700">
            {step.error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <JsonBlock label="Input" data={step.input_data} />
          <JsonBlock label="Output" data={step.output_data} />
        </div>
      </div>
    </details>
  );
}

function JsonBlock({ label, data }: { label: string; data: Record<string, unknown> | null }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        {label}
      </div>
      <pre className="max-h-60 overflow-auto border border-neutral-200 bg-neutral-50 p-2 font-mono text-[11px] text-neutral-800">
        {data ? JSON.stringify(data, null, 2) : "—"}
      </pre>
    </div>
  );
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-neutral-200 bg-white p-3">
      <div className="text-[10px] uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="mt-1 text-[13px] font-medium text-ink">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    SUCCESS: "bg-emerald-50 text-emerald-700 border-emerald-200",
    RUNNING: "bg-blue-50 text-blue-700 border-blue-200",
    PENDING: "bg-neutral-50 text-neutral-600 border-neutral-200",
    ERROR: "bg-red-50 text-red-700 border-red-200",
    CANCELLED: "bg-amber-50 text-amber-700 border-amber-200",
  };
  const cls = map[status] ?? "bg-neutral-50 text-neutral-600 border-neutral-200";
  return (
    <span
      className={`inline-block border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${cls}`}
    >
      {status}
    </span>
  );
}
