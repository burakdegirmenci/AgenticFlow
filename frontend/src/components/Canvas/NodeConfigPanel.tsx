import type { Node as RFNode } from "@xyflow/react";
import { Trash2 } from "lucide-react";

import type { NodeCatalogEntry } from "@/types/node";

interface Props {
  node: RFNode | null;
  catalog: NodeCatalogEntry | null;
  onUpdate: (config: Record<string, unknown>) => void;
  onDelete?: (nodeId: string) => void;
}

interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  enum?: unknown[];
  default?: unknown;
}

export default function NodeConfigPanel({ node, catalog, onUpdate, onDelete }: Props) {
  if (!node || !catalog) {
    return (
      <aside className="flex w-72 shrink-0 flex-col border-l border-neutral-200 bg-white">
        <div className="flex h-12 items-center border-b border-neutral-200 px-4 text-[12px] font-semibold uppercase tracking-wider text-neutral-500">
          Node Ayarları
        </div>
        <div className="p-4 text-[12px] text-neutral-500">Bir node seç.</div>
      </aside>
    );
  }

  const config = (node.data.config ?? {}) as Record<string, unknown>;
  const schema = catalog.config_schema as {
    type?: string;
    properties?: Record<string, SchemaProperty>;
    required?: string[];
  };
  const properties = schema?.properties ?? {};

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-neutral-200 bg-white">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-neutral-200 px-4">
        <span className="truncate text-[12px] font-semibold uppercase tracking-wider text-neutral-500">
          {catalog.display_name}
        </span>
        {onDelete && (
          <button
            type="button"
            onClick={() => onDelete(node.id)}
            title="Node'u sil (Delete / Backspace)"
            className="flex items-center gap-1 border border-red-200 bg-white px-2 py-1 text-[11px] font-medium text-red-600 hover:bg-red-50"
          >
            <Trash2 className="h-3 w-3" strokeWidth={2} />
            Sil
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-4 border border-neutral-200 bg-neutral-50 p-2 font-mono text-[10px] text-neutral-600">
          {catalog.type_id}
        </div>
        {catalog.description && (
          <p className="mb-4 text-[12px] leading-relaxed text-neutral-600">{catalog.description}</p>
        )}

        {Object.keys(properties).length === 0 ? (
          <div className="text-[12px] text-neutral-500">Bu node için config yok.</div>
        ) : (
          <div className="space-y-3">
            {Object.entries(properties).map(([key, prop]) => (
              <FormField
                key={key}
                name={key}
                prop={prop}
                value={config[key]}
                onChange={(v) => onUpdate({ [key]: v })}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

/** Stringify a primitive value for display in an input.
 *
 * Objects and arrays are JSON-encoded so users never see `[object Object]`.
 * `null`/`undefined` become empty string.
 */
function toInputString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

function FormField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = prop.title ?? name;
  const displayValue = toInputString(value ?? prop.default);

  if (prop.enum && prop.enum.length > 0) {
    return (
      <label className="flex flex-col gap-1">
        <span className="text-[11px] font-medium text-neutral-700">{label}</span>
        <select
          value={displayValue}
          onChange={(e) => onChange(e.target.value)}
          className="border border-neutral-300 bg-white px-2 py-1.5 text-[12px] outline-none focus:border-accent"
        >
          <option value="">—</option>
          {prop.enum.map((opt) => (
            <option key={String(opt)} value={String(opt)}>
              {String(opt)}
            </option>
          ))}
        </select>
        {prop.description && (
          <span className="text-[10px] text-neutral-500">{prop.description}</span>
        )}
      </label>
    );
  }

  if (prop.type === "boolean") {
    return (
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={Boolean(value ?? prop.default ?? false)}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="text-[12px] font-medium text-neutral-700">{label}</span>
      </label>
    );
  }

  if (prop.type === "integer" || prop.type === "number") {
    return (
      <label className="flex flex-col gap-1">
        <span className="text-[11px] font-medium text-neutral-700">{label}</span>
        <input
          type="number"
          value={displayValue}
          onChange={(e) => {
            const v = e.target.value;
            onChange(v === "" ? null : Number(v));
          }}
          className="border border-neutral-300 bg-white px-2 py-1.5 text-[12px] outline-none focus:border-accent"
        />
        {prop.description && (
          <span className="text-[10px] text-neutral-500">{prop.description}</span>
        )}
      </label>
    );
  }

  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium text-neutral-700">{label}</span>
      <input
        type="text"
        value={displayValue}
        onChange={(e) => onChange(e.target.value)}
        className="border border-neutral-300 bg-white px-2 py-1.5 text-[12px] outline-none focus:border-accent"
      />
      {prop.description && <span className="text-[10px] text-neutral-500">{prop.description}</span>}
    </label>
  );
}
