import { useQuery } from "@tanstack/react-query";
import { Activity, Database, History, Workflow as WorkflowIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { listExecutions } from "@/api/executions";
import { listSites } from "@/api/sites";
import { listWorkflows } from "@/api/workflows";

export default function Dashboard() {
  const sites = useQuery({ queryKey: ["sites"], queryFn: listSites });
  const workflows = useQuery({
    queryKey: ["workflows"],
    queryFn: listWorkflows,
  });
  const executions = useQuery({
    queryKey: ["executions", { limit: 10 }],
    queryFn: () => listExecutions({ limit: 10 }),
  });

  const stats = [
    {
      label: "Siteler",
      value: sites.data?.length ?? "—",
      icon: Database,
      to: "/sites",
    },
    {
      label: "Workflows",
      value: workflows.data?.length ?? "—",
      icon: WorkflowIcon,
      to: "/workflows",
    },
    {
      label: "Son Çalıştırmalar",
      value: executions.data?.length ?? "—",
      icon: History,
      to: "/executions",
    },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <header className="flex h-14 items-center justify-between border-b border-neutral-200 px-6">
        <h1 className="text-[15px] font-semibold tracking-tight">Dashboard</h1>
      </header>

      <div className="p-6">
        <div className="grid grid-cols-3 gap-4">
          {stats.map(({ label, value, icon: Icon, to }) => (
            <Link
              key={label}
              to={to}
              className="border border-neutral-200 bg-white p-5 transition-colors hover:border-neutral-400"
            >
              <div className="flex items-center justify-between">
                <Icon className="h-4 w-4 text-neutral-500" strokeWidth={1.75} />
                <span className="text-[11px] uppercase tracking-wider text-neutral-500">
                  {label}
                </span>
              </div>
              <div className="mt-4 text-2xl font-semibold text-ink">{value}</div>
            </Link>
          ))}
        </div>

        <section className="mt-8">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4 text-neutral-600" strokeWidth={1.75} />
            <h2 className="text-[13px] font-semibold uppercase tracking-wider text-neutral-600">
              Son Execution'lar
            </h2>
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
                  </tr>
                </thead>
                <tbody>
                  {executions.data.map((e) => (
                    <tr
                      key={e.id}
                      className="border-b border-neutral-100 last:border-0 hover:bg-neutral-50"
                    >
                      <td className="px-4 py-2 font-mono">#{e.id}</td>
                      <td className="px-4 py-2">{e.workflow_id}</td>
                      <td className="px-4 py-2">{e.trigger_type}</td>
                      <td className="px-4 py-2">
                        <StatusBadge status={e.status} />
                      </td>
                      <td className="px-4 py-2 text-neutral-500">
                        {new Date(e.started_at).toLocaleString("tr-TR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-4 text-[13px] text-neutral-500">Henüz execution yok.</div>
            )}
          </div>
        </section>
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
