import {
  Database,
  Headphones,
  History,
  LayoutGrid,
  Settings as SettingsIcon,
  Workflow,
  Zap,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/workflows", label: "Workflows", icon: Workflow },
  { to: "/sites", label: "Sites", icon: Database },
  { to: "/executions", label: "Executions", icon: History },
  { to: "/support", label: "Destek", icon: Headphones },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function Layout() {
  return (
    <div className="flex h-screen w-screen bg-paper text-ink">
      <aside className="flex w-56 flex-col border-r border-neutral-200 bg-white">
        <div className="flex h-14 items-center gap-2 border-b border-neutral-200 px-4">
          <Zap className="h-5 w-5 text-accent" strokeWidth={2} />
          <span className="text-[15px] font-semibold tracking-tight">AgenticFlow</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 px-4 py-2 text-[13px] font-medium",
                  isActive
                    ? "border-l-2 border-accent bg-neutral-100 text-ink"
                    : "border-l-2 border-transparent text-neutral-600 hover:bg-neutral-50 hover:text-ink",
                ].join(" ")
              }
            >
              <Icon className="h-4 w-4" strokeWidth={1.75} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-neutral-200 px-4 py-3 text-[11px] text-neutral-500">
          MVP • v0.1.0
        </div>
      </aside>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
