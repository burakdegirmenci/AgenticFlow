/**
 * RunWorkflowDialog — runtime parameter dialog with Excel preview + column mapping.
 *
 * Flow: Upload → Preview → Map columns → Run
 * Spec: docs/EXCEL_PREVIEW_MAPPING_SPEC.md
 */

import { Upload, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { apiClient } from "@/api/client";

const TICIMAX_FIELDS = [
  { value: "", label: "— Kullanma (atla) —" },
  { value: "StokKodu", label: "Stok Kodu" },
  { value: "UrunKartiID", label: "Ürün ID" },
  { value: "Miktar", label: "Miktar (Stok Adedi)" },
  { value: "Fiyat", label: "Fiyat" },
  { value: "UrunAdi", label: "Ürün Adı" },
  { value: "Aciklama", label: "Açıklama" },
  { value: "OzelAlan1", label: "Özel Alan 1" },
  { value: "OzelAlan2", label: "Özel Alan 2" },
  { value: "Barkod", label: "Barkod" },
  { value: "Marka", label: "Marka" },
  { value: "Kategori", label: "Kategori" },
] as const;

interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  format?: string;
}

interface InputSchema {
  type: string;
  properties: Record<string, SchemaProperty>;
  required?: string[];
}

interface PreviewData {
  filename: string;
  columns: string[];
  sample_rows: Record<string, unknown>[];
  total_rows: number;
}

interface Props {
  workflowId: number;
  inputSchema: InputSchema;
  onClose: () => void;
  onRun: (inputData: Record<string, unknown>) => void;
  isRunning: boolean;
}

export default function RunWorkflowDialog({
  workflowId: _wid,
  inputSchema,
  onClose,
  onRun,
  isRunning,
}: Props) {
  const properties = inputSchema.properties ?? {};
  const required = new Set(inputSchema.required ?? []);

  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const init: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries(properties)) {
      if (prop.default !== undefined) init[key] = prop.default;
    }
    return init;
  });

  const [uploading, setUploading] = useState(false);
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [originalName, setOriginalName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});

  const fileFieldKey = Object.entries(properties).find(
    ([, p]) => p.format === "file-upload",
  )?.[0];

  const setValue = useCallback((key: string, val: unknown) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  const handleFileUpload = useCallback(
    async (file: File) => {
      if (!fileFieldKey) return;
      setUploading(true);
      setPreview(null);
      setColumnMapping({});
      try {
        const form = new FormData();
        form.append("file", file);
        const uploadResp = await apiClient.post<{ filename: string; original: string }>(
          "/uploads",
          form,
          { headers: { "Content-Type": "multipart/form-data" } },
        );
        const { filename, original } = uploadResp.data;
        setUploadedFilename(filename);
        setOriginalName(original);
        setValue(fileFieldKey, filename);

        const previewResp = await apiClient.get<PreviewData>(
          `/uploads/${encodeURIComponent(filename)}/preview`,
        );
        setPreview(previewResp.data);

        // Auto-map: try matching column names to known fields
        const autoMap: Record<string, string> = {};
        for (const col of previewResp.data.columns) {
          const lc = col.toLowerCase().replace(/[\s_-]+/g, "");
          const match = TICIMAX_FIELDS.find((f) => {
            if (!f.value) return false;
            return (
              f.value.toLowerCase() === lc ||
              f.label.toLowerCase().replace(/[\s_()-]+/g, "") === lc
            );
          });
          if (match) autoMap[match.value] = col;
        }
        setColumnMapping(autoMap);
      } catch (e) {
        alert(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [fileFieldKey, setValue],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (fileFieldKey && !uploadedFilename) {
      alert("Dosya yüklenmedi.");
      return;
    }
    for (const key of required) {
      if (key === fileFieldKey) continue;
      const v = values[key];
      if (v === undefined || v === null || v === "") {
        alert(`"${properties[key]?.title ?? key}" zorunludur.`);
        return;
      }
    }
    const inputData: Record<string, unknown> = { ...values };
    if (Object.keys(columnMapping).length > 0) {
      inputData.column_map = columnMapping;
    }
    onRun(inputData);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto border border-neutral-200 bg-white shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white px-5 py-3">
          <h2 className="text-[14px] font-semibold">Çalıştırma Parametreleri</h2>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-700">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 p-5">
          {/* ---- File upload ---- */}
          {fileFieldKey && (
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label className="text-[12px] font-medium text-neutral-700">
                  {properties[fileFieldKey]?.title ?? "Dosya"}{" "}
                  <span className="text-red-500">*</span>
                </label>
                {properties[fileFieldKey]?.description && (
                  <span className="text-[10px] text-neutral-500">
                    {properties[fileFieldKey]?.description}
                  </span>
                )}
                <div className="flex items-center gap-2">
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xlsx,.csv"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) void handleFileUpload(f);
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    className="flex items-center gap-1.5 border border-neutral-300 bg-white px-3 py-1.5 text-[12px] hover:bg-neutral-50 disabled:opacity-50"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    {uploading ? "Yükleniyor…" : "Dosya Seç"}
                  </button>
                  {originalName && (
                    <span className="text-[11px] text-emerald-700">✓ {originalName}</span>
                  )}
                </div>
              </div>

              {/* ---- Preview table ---- */}
              {preview && preview.columns.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-[12px] font-semibold text-neutral-600">
                    Önizleme ({preview.total_rows} satır)
                  </h3>
                  <div className="overflow-x-auto border border-neutral-200">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="border-b border-neutral-200 bg-neutral-50">
                          {preview.columns.map((col) => (
                            <th key={col} className="px-2 py-1.5 text-left font-medium text-neutral-600">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.sample_rows.slice(0, 3).map((row, i) => (
                          <tr key={i} className="border-b border-neutral-100">
                            {preview.columns.map((col) => (
                              <td key={col} className="px-2 py-1 text-neutral-700">
                                {row[col] != null ? String(row[col]) : "—"}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* ---- Column mapping ---- */}
                  <div className="space-y-2">
                    <h3 className="text-[12px] font-semibold text-neutral-600">
                      Kolon Eşlemesi
                    </h3>
                    <p className="text-[10px] text-neutral-500">
                      Her Excel kolonunun Ticimax karşılığını seçin.
                    </p>
                    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                      {preview.columns.map((col) => {
                        const mappedTo = Object.entries(columnMapping).find(
                          ([, src]) => src === col,
                        )?.[0];
                        return (
                          <div key={col} className="flex items-center gap-1.5">
                            <span className="w-24 truncate text-[11px] font-medium text-neutral-700" title={col}>
                              {col}
                            </span>
                            <span className="text-[11px] text-neutral-400">→</span>
                            <select
                              value={mappedTo ?? ""}
                              onChange={(e) => {
                                const target = e.target.value;
                                setColumnMapping((prev) => {
                                  const next = { ...prev };
                                  // Remove old mapping for this column
                                  for (const [k, v] of Object.entries(next)) {
                                    if (v === col) delete next[k];
                                  }
                                  if (target) next[target] = col;
                                  return next;
                                });
                              }}
                              className="flex-1 border border-neutral-200 bg-white px-1.5 py-1 text-[11px] focus:border-accent focus:outline-none"
                            >
                              {TICIMAX_FIELDS.map((f) => (
                                <option key={f.value} value={f.value}>
                                  {f.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ---- Non-file fields ---- */}
          {Object.entries(properties)
            .filter(([key]) => key !== fileFieldKey)
            .map(([key, prop]) =>
              prop.type === "boolean" ? (
                <label key={key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(values[key])}
                    onChange={(e) => setValue(key, e.target.checked)}
                    className="h-4 w-4"
                  />
                  <span className="text-[12px] text-neutral-700">{prop.title ?? key}</span>
                </label>
              ) : (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-[12px] font-medium text-neutral-700">
                    {prop.title ?? key}
                  </label>
                  <input
                    type={prop.type === "integer" || prop.type === "number" ? "number" : "text"}
                    value={String(values[key] ?? "")}
                    onChange={(e) => setValue(key, e.target.value)}
                    className="border border-neutral-300 px-2 py-1.5 text-[12px] outline-none focus:border-accent"
                  />
                </div>
              ),
            )}

          {/* ---- Footer ---- */}
          <div className="flex items-center justify-between border-t border-neutral-100 pt-3">
            <span className="text-[10px] text-neutral-500">
              {preview
                ? `${Object.keys(columnMapping).length} kolon eşlendi / ${preview.columns.length} toplam`
                : "Dosya seçince önizleme gösterilecek"}
            </span>
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className="border border-neutral-300 px-4 py-1.5 text-[12px] hover:bg-neutral-50">
                İptal
              </button>
              <button
                type="submit"
                disabled={isRunning || uploading || (!!fileFieldKey && !uploadedFilename)}
                className="border border-accent bg-accent px-4 py-1.5 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {isRunning ? "Çalıştırılıyor…" : "Çalıştır"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
