/**
 * RunWorkflowDialog — modal that prompts for runtime parameters before
 * executing a workflow.
 *
 * When a workflow has `input_schema`, clicking "Run" opens this dialog
 * instead of immediately starting the execution. The dialog renders a
 * form from the JSON Schema, handles file uploads via POST /api/uploads,
 * and submits the collected `input_data` to POST /api/workflows/:id/run.
 *
 * When there is no `input_schema`, the caller should skip this dialog
 * and run directly (backward-compatible with existing workflows).
 *
 * Spec: docs/RUNTIME_INPUT_SPEC.md
 */

import { Upload, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { apiClient } from "@/api/client";

interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  format?: string;
  enum?: unknown[];
  enumNames?: string[];
}

interface InputSchema {
  type: string;
  properties: Record<string, SchemaProperty>;
  required?: string[];
}

interface Props {
  workflowId: number;
  inputSchema: InputSchema;
  onClose: () => void;
  onRun: (inputData: Record<string, unknown>) => void;
  isRunning: boolean;
}

export default function RunWorkflowDialog({
  workflowId: _workflowId,
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
      if (prop.default !== undefined) {
        init[key] = prop.default;
      }
    }
    return init;
  });

  const [uploading, setUploading] = useState<Record<string, boolean>>({});
  const [uploadedFiles, setUploadedFiles] = useState<Record<string, string>>({});
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const setValue = useCallback((key: string, val: unknown) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  const handleFileUpload = useCallback(
    async (key: string, file: File) => {
      setUploading((prev) => ({ ...prev, [key]: true }));
      try {
        const form = new FormData();
        form.append("file", file);
        const resp = await apiClient.post<{ filename: string }>("/uploads", form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const filename = resp.data.filename;
        setValue(key, filename);
        setUploadedFiles((prev) => ({ ...prev, [key]: file.name }));
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Upload failed";
        alert(msg);
      } finally {
        setUploading((prev) => ({ ...prev, [key]: false }));
      }
    },
    [setValue],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Validate required
    for (const key of required) {
      const v = values[key];
      if (v === undefined || v === null || v === "") {
        alert(`"${properties[key]?.title ?? key}" alanı zorunludur.`);
        return;
      }
    }
    onRun(values);
  };

  const anyUploading = Object.values(uploading).some(Boolean);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg border border-neutral-200 bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-3">
          <h2 className="text-[14px] font-semibold">Çalıştırma Parametreleri</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700"
            aria-label="Kapat"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          {Object.entries(properties).map(([key, prop]) => {
            const isFileUpload = prop.format === "file-upload";
            const label = prop.title ?? key;
            const isReq = required.has(key);

            if (isFileUpload) {
              return (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-[12px] font-medium text-neutral-700">
                    {label} {isReq && <span className="text-red-500">*</span>}
                  </label>
                  {prop.description && (
                    <span className="text-[10px] text-neutral-500">{prop.description}</span>
                  )}
                  <div className="flex items-center gap-2">
                    <input
                      ref={(el) => {
                        fileRefs.current[key] = el;
                      }}
                      type="file"
                      accept=".xlsx,.csv"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void handleFileUpload(key, f);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => fileRefs.current[key]?.click()}
                      disabled={uploading[key]}
                      className="flex items-center gap-1.5 border border-neutral-300 bg-white px-3 py-1.5 text-[12px] hover:bg-neutral-50 disabled:opacity-50"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      {uploading[key] ? "Yükleniyor…" : "Dosya Seç"}
                    </button>
                    {uploadedFiles[key] && (
                      <span className="text-[11px] text-emerald-700">
                        ✓ {uploadedFiles[key]}
                      </span>
                    )}
                  </div>
                </div>
              );
            }

            if (prop.type === "boolean") {
              return (
                <label key={key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(values[key])}
                    onChange={(e) => setValue(key, e.target.checked)}
                    className="h-4 w-4 border-neutral-300"
                  />
                  <span className="text-[12px] font-medium text-neutral-700">{label}</span>
                  {prop.description && (
                    <span className="text-[10px] text-neutral-500">— {prop.description}</span>
                  )}
                </label>
              );
            }

            if (prop.enum) {
              return (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-[12px] font-medium text-neutral-700">
                    {label} {isReq && <span className="text-red-500">*</span>}
                  </label>
                  <select
                    value={String(values[key] ?? prop.default ?? "")}
                    onChange={(e) => setValue(key, e.target.value)}
                    className="border border-neutral-300 bg-white px-2 py-1.5 text-[12px] outline-none focus:border-accent"
                  >
                    {prop.enum.map((opt, i) => (
                      <option key={String(opt)} value={String(opt)}>
                        {prop.enumNames?.[i] ?? String(opt)}
                      </option>
                    ))}
                  </select>
                </div>
              );
            }

            // Default: text / number input
            return (
              <div key={key} className="flex flex-col gap-1">
                <label className="text-[12px] font-medium text-neutral-700">
                  {label} {isReq && <span className="text-red-500">*</span>}
                </label>
                {prop.description && (
                  <span className="text-[10px] text-neutral-500">{prop.description}</span>
                )}
                <input
                  type={prop.type === "integer" || prop.type === "number" ? "number" : "text"}
                  value={String(values[key] ?? prop.default ?? "")}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (prop.type === "integer") setValue(key, raw === "" ? null : parseInt(raw, 10));
                    else if (prop.type === "number")
                      setValue(key, raw === "" ? null : parseFloat(raw));
                    else setValue(key, raw);
                  }}
                  className="border border-neutral-300 bg-white px-2 py-1.5 text-[12px] outline-none focus:border-accent"
                />
              </div>
            );
          })}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="border border-neutral-300 bg-white px-4 py-1.5 text-[12px] hover:bg-neutral-50"
            >
              İptal
            </button>
            <button
              type="submit"
              disabled={isRunning || anyUploading}
              className="border border-accent bg-accent px-4 py-1.5 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {isRunning ? "Çalıştırılıyor…" : "Çalıştır"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
