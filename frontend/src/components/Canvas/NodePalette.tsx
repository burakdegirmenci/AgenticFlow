import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { type DragEvent, useMemo, useState } from "react";

import type { NodeCatalogEntry } from "@/types/node";

import { getNodeIcon } from "./iconMap";

interface Props {
  catalog: NodeCatalogEntry[];
  onAdd: (typeId: string) => void;
}

const CATEGORY_ORDER = ["trigger", "ticimax", "transform", "logic", "ai", "output"];

const CATEGORY_LABEL: Record<string, string> = {
  trigger: "Tetikleyiciler",
  ticimax: "Ticimax",
  transform: "Dönüşüm",
  logic: "Mantık",
  ai: "Yapay Zeka",
  output: "Çıktı",
};

/**
 * MIME type used to encode the dragged node type when dropping onto the
 * canvas. Read by `WorkflowEditor`'s onDrop handler.
 */
export const NODE_DRAG_MIME = "application/x-agenticflow-node-type";

function handleDragStart(typeId: string) {
  return (event: DragEvent<HTMLButtonElement>) => {
    event.dataTransfer.setData(NODE_DRAG_MIME, typeId);
    event.dataTransfer.setData("text/plain", typeId);
    event.dataTransfer.effectAllowed = "move";
  };
}

export default function NodePalette({ catalog, onAdd }: Props) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const grouped = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = catalog.filter(
      (n) =>
        !q ||
        n.display_name.toLowerCase().includes(q) ||
        n.type_id.toLowerCase().includes(q) ||
        (n.description && n.description.toLowerCase().includes(q)),
    );
    const groups: Record<string, NodeCatalogEntry[]> = {};
    for (const node of filtered) {
      (groups[node.category] ??= []).push(node);
    }
    return groups;
  }, [catalog, search]);

  const toggle = (cat: string) => setCollapsed((c) => ({ ...c, [cat]: !c[cat] }));

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 p-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-400"
            strokeWidth={2}
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Node ara…"
            className="w-full border border-neutral-300 bg-white py-1.5 pl-7 pr-2 text-[12px] outline-none focus:border-accent"
          />
        </div>
        <div className="mt-2 text-[10px] text-neutral-400">
          Sürükleyip canvas'a bırakın veya tıklayın
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {CATEGORY_ORDER.map((cat) => {
          const items = grouped[cat];
          if (!items || items.length === 0) return null;
          const isCollapsed = !!collapsed[cat] && !search;
          return (
            <div key={cat} className="border-b border-neutral-100">
              <button
                type="button"
                onClick={() => toggle(cat)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-neutral-500 hover:bg-neutral-50"
              >
                <span className="flex items-center gap-1">
                  {isCollapsed ? (
                    <ChevronRight className="h-3 w-3" strokeWidth={2.5} />
                  ) : (
                    <ChevronDown className="h-3 w-3" strokeWidth={2.5} />
                  )}
                  {CATEGORY_LABEL[cat] ?? cat}
                </span>
                <span className="text-[10px] font-normal text-neutral-400">{items.length}</span>
              </button>
              {!isCollapsed && (
                <div className="pb-2">
                  {items.map((node) => {
                    const Icon = getNodeIcon(node.icon);
                    return (
                      <button
                        key={node.type_id}
                        draggable
                        onDragStart={handleDragStart(node.type_id)}
                        onClick={() => onAdd(node.type_id)}
                        className="group flex w-full cursor-grab items-center gap-2 px-3 py-1.5 text-left text-[12px] text-neutral-700 hover:bg-neutral-50 active:cursor-grabbing"
                        title={node.description || node.type_id}
                      >
                        <span
                          className="flex h-6 w-6 shrink-0 items-center justify-center"
                          style={{ backgroundColor: `${node.color}15` }}
                        >
                          <Icon
                            className="h-3.5 w-3.5"
                            strokeWidth={2}
                            style={{ color: node.color }}
                          />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-ink">
                            {node.display_name}
                          </span>
                          <span className="block truncate text-[10px] text-neutral-400">
                            {node.type_id}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {catalog.length === 0 && (
          <div className="p-3 text-[12px] text-neutral-500">Node bulunamadı.</div>
        )}
      </div>
    </aside>
  );
}
