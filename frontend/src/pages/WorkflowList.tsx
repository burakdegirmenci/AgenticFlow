import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listSites } from "@/api/sites";
import { createWorkflow, deleteWorkflow, listWorkflows, runWorkflow } from "@/api/workflows";

export default function WorkflowList() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    site_id: 0,
  });

  const workflows = useQuery({
    queryKey: ["workflows"],
    queryFn: listWorkflows,
  });
  const sites = useQuery({ queryKey: ["sites"], queryFn: listSites });

  const createMut = useMutation({
    mutationFn: createWorkflow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflows"] });
      setShowForm(false);
      setForm({ name: "", description: "", site_id: 0 });
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteWorkflow,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workflows"] }),
  });

  const runMut = useMutation({
    mutationFn: (id: number) => runWorkflow(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["executions"] }),
  });

  return (
    <div className="h-full overflow-y-auto">
      <header className="flex h-14 items-center justify-between border-b border-neutral-200 px-6">
        <h1 className="text-[15px] font-semibold tracking-tight">Workflows</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          disabled={!sites.data || sites.data.length === 0}
          className="flex items-center gap-1.5 border border-ink bg-ink px-3 py-1.5 text-[12px] font-medium text-white hover:bg-neutral-800 disabled:opacity-40"
        >
          <Plus className="h-3.5 w-3.5" strokeWidth={2} />
          Yeni Workflow
        </button>
      </header>

      <div className="p-6">
        {sites.data && sites.data.length === 0 && (
          <div className="mb-4 border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800">
            Workflow oluşturmadan önce{" "}
            <Link to="/sites" className="underline">
              en az bir site ekle
            </Link>
            .
          </div>
        )}

        {showForm && sites.data && sites.data.length > 0 && (
          <form
            className="mb-6 border border-neutral-200 bg-white p-5"
            onSubmit={(e) => {
              e.preventDefault();
              createMut.mutate({
                name: form.name,
                description: form.description || null,
                site_id: form.site_id || sites.data[0].id,
              });
            }}
          >
            <h2 className="mb-4 text-[13px] font-semibold uppercase tracking-wider text-neutral-600">
              Yeni Workflow
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-[11px] uppercase tracking-wider text-neutral-500">İsim</span>
                <input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  required
                  className="border border-neutral-300 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[11px] uppercase tracking-wider text-neutral-500">
                  Açıklama
                </span>
                <input
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  className="border border-neutral-300 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[11px] uppercase tracking-wider text-neutral-500">Site</span>
                <select
                  value={form.site_id || sites.data[0].id}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      site_id: Number(e.target.value),
                    }))
                  }
                  className="border border-neutral-300 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-accent"
                >
                  {sites.data.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.domain})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={createMut.isPending}
                className="border border-accent bg-accent px-3 py-1.5 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {createMut.isPending ? "Oluşturuluyor…" : "Oluştur"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="border border-neutral-300 bg-white px-3 py-1.5 text-[12px] font-medium text-neutral-700 hover:bg-neutral-50"
              >
                İptal
              </button>
            </div>
          </form>
        )}

        <div className="border border-neutral-200 bg-white">
          {workflows.isLoading ? (
            <div className="p-4 text-[13px] text-neutral-500">Yükleniyor…</div>
          ) : workflows.data && workflows.data.length > 0 ? (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-neutral-200 text-left text-[11px] uppercase tracking-wider text-neutral-500">
                  <th className="px-4 py-2 font-medium">ID</th>
                  <th className="px-4 py-2 font-medium">İsim</th>
                  <th className="px-4 py-2 font-medium">Site</th>
                  <th className="px-4 py-2 font-medium">Durum</th>
                  <th className="px-4 py-2 font-medium">Güncellenme</th>
                  <th className="px-4 py-2 text-right font-medium">Aksiyon</th>
                </tr>
              </thead>
              <tbody>
                {workflows.data.map((wf) => {
                  const site = sites.data?.find((s) => s.id === wf.site_id);
                  return (
                    <tr
                      key={wf.id}
                      className="border-b border-neutral-100 last:border-0 hover:bg-neutral-50"
                    >
                      <td className="px-4 py-2 font-mono">#{wf.id}</td>
                      <td className="px-4 py-2 font-medium">
                        <Link to={`/workflows/${wf.id}`} className="text-ink hover:text-accent">
                          {wf.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-neutral-600">
                        {site?.name ?? `#${wf.site_id}`}
                      </td>
                      <td className="px-4 py-2">
                        {wf.is_active ? (
                          <span className="inline-block border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                            Aktif
                          </span>
                        ) : (
                          <span className="inline-block border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[11px] font-medium text-neutral-600">
                            Pasif
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-neutral-500">
                        {new Date(wf.updated_at).toLocaleString("tr-TR")}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => runMut.mutate(wf.id)}
                            disabled={runMut.isPending && runMut.variables === wf.id}
                            className="flex items-center gap-1 border border-neutral-300 bg-white px-2 py-1 text-[11px] text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
                          >
                            <Play className="h-3 w-3" strokeWidth={2} />
                            Run
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`"${wf.name}" silinsin mi?`)) deleteMut.mutate(wf.id);
                            }}
                            className="flex items-center border border-neutral-300 bg-white px-2 py-1 text-[11px] text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="h-3 w-3" strokeWidth={2} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="p-4 text-[13px] text-neutral-500">Henüz workflow yok.</div>
          )}
        </div>
      </div>
    </div>
  );
}
