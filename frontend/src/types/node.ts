export type NodeCategory = "trigger" | "ticimax" | "transform" | "logic" | "ai" | "output";

export interface NodeCatalogEntry {
  type_id: string;
  category: NodeCategory;
  display_name: string;
  description: string;
  icon: string;
  color: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  config_schema: Record<string, unknown>;
}
