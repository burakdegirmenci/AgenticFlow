import {
  BarChart2,
  Box,
  Braces,
  Clock,
  Download,
  Edit3,
  FileSpreadsheet,
  FileText,
  Filter,
  GitBranch,
  GitMerge,
  type LucideIcon,
  Package,
  Play,
  Repeat,
  Save,
  Scissors,
  Search,
  ShoppingCart,
  Shuffle,
  Sparkles,
  Tag,
  Trash2,
  Zap,
} from "lucide-react";

/**
 * Maps the kebab-case icon names emitted by the backend node catalog
 * to lucide-react components. New names should be added here as nodes
 * adopt them; unknown names fall back to `Box` so the canvas never breaks.
 */
const ICON_MAP: Record<string, LucideIcon> = {
  "bar-chart-2": BarChart2,
  box: Box,
  braces: Braces,
  clock: Clock,
  download: Download,
  "edit-3": Edit3,
  "file-spreadsheet": FileSpreadsheet,
  "file-text": FileText,
  filter: Filter,
  "git-branch": GitBranch,
  "git-merge": GitMerge,
  package: Package,
  play: Play,
  repeat: Repeat,
  save: Save,
  scissors: Scissors,
  search: Search,
  "shopping-cart": ShoppingCart,
  shuffle: Shuffle,
  sparkles: Sparkles,
  tag: Tag,
  "trash-2": Trash2,
  zap: Zap,
};

export function getNodeIcon(name: string | undefined | null): LucideIcon {
  if (!name) return Box;
  return ICON_MAP[name] ?? Box;
}
