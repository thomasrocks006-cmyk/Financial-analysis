"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  PlayCircle,
  FileText,
  BarChart3,
  History,
  Settings,
  Activity,
  Shield,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/runs/new", label: "New Run", icon: PlayCircle },
  { href: "/runs", label: "Active Runs", icon: Activity },
  { href: "/saved", label: "Saved Runs", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 flex-col border-r border-[var(--border)] bg-[var(--surface)]">
      {/* Logo / Brand */}
      <div className="flex h-14 items-center gap-2 border-b border-[var(--border)] px-4">
        <BarChart3 className="h-6 w-6 text-[var(--accent)]" />
        <span className="text-sm font-semibold tracking-tight">
          AI Research Platform
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive =
            href === "/"
              ? pathname === "/"
              : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-[var(--accent)]/10 text-[var(--accent)] font-medium"
                  : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[var(--border)] p-4">
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <Shield className="h-3 w-3" />
          <span>v1.0 — Session 16</span>
        </div>
      </div>
    </aside>
  );
}
