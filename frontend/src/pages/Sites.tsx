import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Trash2, XCircle, Zap } from "lucide-react";
import { useState } from "react";

import {
  createSite,
  deleteSite,
  listSites,
  type Site,
  type SiteConnectionTest,
  testSiteConnection,
} from "@/api/sites";

export default function Sites() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", domain: "", uye_kodu: "" });
  const [testResults, setTestResults] = useState<Record<number, SiteConnectionTest>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["sites"],
    queryFn: listSites,
  });

  const createMut = useMutation({
    mutationFn: createSite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      setShowForm(false);
      setForm({ name: "", domain: "", uye_kodu: "" });
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteSite,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });

  const testMut = useMutation({
    mutationFn: (id: number) => testSiteConnection(id),
    onSuccess: (result, id) => setTestResults((prev) => ({ ...prev, [id]: result })),
  });

  return (
    <div className="h-full overflow-y-auto">
      <header className="flex h-14 items-center justify-between border-b border-neutral-200 px-6">
        <h1 className="text-[15px] font-semibold tracking-tight">Ticimax Siteleri</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 border border-ink bg-ink px-3 py-1.5 text-[12px] font-medium text-white hover:bg-neutral-800"
        >
          <Plus className="h-3.5 w-3.5" strokeWidth={2} />
          Site Ekle
        </button>
      </header>

      <div className="p-6">
        {showForm && (
          <form
            className="mb-6 border border-neutral-200 bg-white p-5"
            onSubmit={(e) => {
              e.preventDefault();
              createMut.mutate(form);
            }}
          >
            <h2 className="mb-4 text-[13px] font-semibold uppercase tracking-wider text-neutral-600">
              Yeni Site
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <Field
                label="İsim"
                value={form.name}
                onChange={(v) => setForm((f) => ({ ...f, name: v }))}
                placeholder="Demo Store"
              />
              <Field
                label="Domain"
                value={form.domain}
                onChange={(v) => setForm((f) => ({ ...f, domain: v }))}
                placeholder="demo.example.com"
              />
              <Field
                label="Üye Kodu"
                value={form.uye_kodu}
                onChange={(v) => setForm((f) => ({ ...f, uye_kodu: v }))}
                placeholder="FONxXXXXXXXXX..."
                type="password"
              />
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="submit"
                disabled={createMut.isPending}
                className="border border-accent bg-accent px-3 py-1.5 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {createMut.isPending ? "Kaydediliyor…" : "Kaydet"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="border border-neutral-300 bg-white px-3 py-1.5 text-[12px] font-medium text-neutral-700 hover:bg-neutral-50"
              >
                İptal
              </button>
            </div>
            {createMut.isError && (
              <div className="mt-3 border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {createMut.error.message}
              </div>
            )}
          </form>
        )}

        <div className="border border-neutral-200 bg-white">
          {isLoading ? (
            <div className="p-4 text-[13px] text-neutral-500">Yükleniyor…</div>
          ) : data && data.length > 0 ? (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-neutral-200 text-left text-[11px] uppercase tracking-wider text-neutral-500">
                  <th className="px-4 py-2 font-medium">ID</th>
                  <th className="px-4 py-2 font-medium">İsim</th>
                  <th className="px-4 py-2 font-medium">Domain</th>
                  <th className="px-4 py-2 font-medium">Bağlantı</th>
                  <th className="px-4 py-2 text-right font-medium">Aksiyon</th>
                </tr>
              </thead>
              <tbody>
                {data.map((site: Site) => {
                  const result = testResults[site.id];
                  return (
                    <tr
                      key={site.id}
                      className="border-b border-neutral-100 last:border-0 hover:bg-neutral-50"
                    >
                      <td className="px-4 py-2 font-mono">#{site.id}</td>
                      <td className="px-4 py-2 font-medium">{site.name}</td>
                      <td className="px-4 py-2 text-neutral-600">{site.domain}</td>
                      <td className="px-4 py-2">
                        {result ? (
                          result.status === "ok" ? (
                            <span className="inline-flex items-center gap-1 text-emerald-700">
                              <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />
                              OK
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-red-700">
                              <XCircle className="h-3.5 w-3.5" strokeWidth={2} />
                              HATA
                            </span>
                          )
                        ) : (
                          <span className="text-neutral-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => testMut.mutate(site.id)}
                            disabled={testMut.isPending && testMut.variables === site.id}
                            className="flex items-center gap-1 border border-neutral-300 bg-white px-2 py-1 text-[11px] text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
                          >
                            <Zap className="h-3 w-3" strokeWidth={2} />
                            Test
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`"${site.name}" silinsin mi?`)) deleteMut.mutate(site.id);
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
            <div className="p-4 text-[13px] text-neutral-500">Henüz site eklenmedi.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wider text-neutral-500">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="border border-neutral-300 bg-white px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-accent"
      />
    </label>
  );
}
