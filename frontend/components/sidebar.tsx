"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import { dashboardNav } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 hidden h-screen w-72 shrink-0 border-r border-border/70 bg-card/70 px-5 py-6 backdrop-blur xl:block">
      <div className="flex h-full flex-col">
        <Link href="/dashboard" className="flex items-center gap-3 rounded-2xl px-3 py-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-glow">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-primary">Meeting Bot</p>
            <h2 className="text-lg font-semibold">Control Center</h2>
          </div>
        </Link>

        <nav className="mt-8 space-y-2">
          {dashboardNav.map((item) => {
            const isActive = item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-muted-foreground transition hover:bg-secondary/70 hover:text-foreground",
                  isActive && "bg-primary/10 text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.title}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto rounded-3xl border border-border/60 bg-background/70 p-5">
          <p className="text-sm font-semibold">Always-on meeting teammate</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Join meetings, answer out loud, and ship clean reports without context switching.
          </p>
        </div>
      </div>
    </aside>
  );
}
