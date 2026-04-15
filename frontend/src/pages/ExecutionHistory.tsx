import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listExecutions } from "@/api/executions";
import { listWorkflows } from "@/api/workflows";

const STATUS_OPTIONS = ["", "SUCCESS", "ERROR", "RUNNING", "PENDING", "CANCELLED"];
const TRIGGER_OPTIONS = ["", "MANUAL", "SCHEDULE", "POLLING", "AGENT"];

export default function ExecutionHistory() {
  const [statusFilter, setStatusFilter] = useState("");
  const [triggerFilter, setTriggerFilter] = useState("");
  const [search, setSearch] = useState("");
  // debounced search: local input is live, query key uses committed value
  const [committedSearch, setCommittedSearch] = useState("");

  const executions = useQuery({
    queryKey: [
      "executions",
      {
        limit: 100,
        status: statusFilter,
        trigger_type: triggerFilter,
        search: committedSearch,
      },
    ],
    queryFn: () =>
      listExecutions({
        limit: 100,
        status: statusFilter || undefined,
        trigger_type: triggerFilter || undefined,
        search: committedSearch || undefined,
      }),
    refetchInterval: 5_000,
  });

  const workflows = useQuery({
    queryKey: ["workflows"],
    queryFn: listWorkflows,
  });

  const wfName = (id: number) => workflows.data?.find((w) => w.id === id)?.name ?? `#${id}`;

  const handleSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setCommittedSearch(search);
    }
  };

  const handleClear = () => {
    setStatusFilter("");
    setTriggerFilter("");
    setSearch("");
    setCommittedSearch("");
  };

  const hasFilters = statusFilter !== "" || triggerFilter !== "" || committedSearch !== "";

  return (
    <div className="h-full overflow-y-auto">
      <header className="flex h-14 items-center justify-between border-b border-neutral-200 px-6">
        <h1 className="text-[15px] font-semibold tracking-tight">Execution History</h1>
      </header>

      <div className="p-6">
        {/* Filter bar */}
        <div className="mb-4 flex flex-wrap items-end gap-3 border border-neutral-200 bg-white p-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-neutral-500">Durum</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-8 min-w-[120px] border border-neutral-200 bg-white px-2 text-[13px] focus:border-accent focus:outline-none"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s || "— Tümü —"}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-neutral-500">Trigger</label>
            <select
              value={triggerFilter}
              onChange={(e) => setTriggerFilter(e.target.value)}
              className="h-8 min-w-[120px] border border-neutral-200 bg-white px-2 text-[13px] focus:border-accent focus:outline-none"
            >
              {TRIGGER_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t || "— Tümü —"}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-1 flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-neutral-500">
              Ara (workflow adı veya hata)
            </label>
            <div className="flex gap-2">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={handleSearchKey}
                placeholder="Enter'a bas"
                className="h-8 flex-1 border border-neutral-200 bg-white px-2 text-[13px] focus:border-accent focus:outline-none"
              />
              <button
                onClick={() => setCommittedSearch(search)}
                className="h-8 border border-neutral-200 bg-white px-3 text-[12px] hover:bg-neutral-50"
              >
                Ara
              </button>
            </div>
          </div>

          {hasFilters && (
            <button
              onClick={handleClear}
              className="h-8 self-end border border-neutral-200 bg-white px-3 text-[12px] text-neutral-600 hover:bg-neutral-50"
            >
              Temizle
            </button>
          )}
        </div>

        <div className="border border-neutral-200 bg-white">
          {executions.isLoading ? (
            <div className="p-4 text-[13px] text-neutral-500">Yükleniyor…</div>
          ) : executions.data && executions.data.length > 0 ? (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-neutral-200 text-left text-[11px] uppercase tracking-wider text-neutral-500">
                  <th className="px-4 py-2 font-medium">ID</th>
                  <th className="px-4 py-2 font-medium">Workflow</th>
                  <th className="px-4 py-2 font-medium">Trigger</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Başlangıç</th>
                  <th className="px-4 py-2 font-medium">Süre</th>
                </tr>
              </thead>
              <tbody>
                {executions.data.map((e) => {
                  const duration =
                    e.finished_at && e.started_at
                      ? (new Date(e.finished_at).getTime() - new Date(e.started_at).getTime()) /
                        1000
                      : null;
                  return (
                    <tr
                      key={e.id}
                      className="border-b border-neutral-100 last:border-0 hover:bg-neutral-50"
                    >
                      <td className="px-4 py-2 font-mono">
                        <Link to={`/executions/${e.id}`} className="text-ink hover:text-accent">
                          #{e.id}
                        </Link>
                      </td>
                      <td className="px-4 py-2">{wfName(e.workflow_id)}</td>
                      <td className="px-4 py-2 text-neutral-600">{e.trigger_type}</td>
                      <td className="px-4 py-2">
                        <StatusBadge status={e.status} />
                      </td>
                      <td className="px-4 py-2 text-neutral-500">
                        {new Date(e.started_at).toLocaleString("tr-TR")}
                      </td>
                      <td className="px-4 py-2 font-mono text-neutral-500">
                        {duration !== null ? `${duration.toFixed(2)}s` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="p-4 text-[13px] text-neutral-500">
              {hasFilters ? "Filtrelere uyan execution bulunamadı." : "Henüz execution yok."}
            </div>
          )}
        </div>
      </div>
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
    <span className={`inline-block border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {status}
    </span>
  );
}
