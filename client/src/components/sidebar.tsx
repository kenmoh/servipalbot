"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Users, 
  Mail, 
  Settings, 
  ShieldCheck, 
  FileText,
  Activity
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Leads", href: "/leads", icon: Users },
  { name: "Emails", href: "/emails", icon: Mail },
  { name: "Logs", href: "/logs", icon: FileText },
  { name: "System Health", href: "/health", icon: Activity },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-card border-r border-border text-foreground w-64 transition-all">
      <div className="flex h-16 shrink-0 items-center px-6 border-b border-border">
        <ShieldCheck className="h-8 w-8 text-primary" />
        <span className="ml-3 text-lg font-bold tracking-tight text-foreground">ServiPal</span>
      </div>
      <nav className="flex flex-1 flex-col p-4">
        <ul role="list" className="flex flex-1 flex-col gap-y-7">
          <li>
            <ul role="list" className="-mx-2 space-y-1">
              {navigation.map((item) => (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    className={cn(
                      pathname === item.href
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50",
                      "group flex gap-x-3 rounded-md p-2 text-sm font-semibold leading-6 transition-colors"
                    )}
                  >
                    <item.icon
                      className={cn(
                        pathname === item.href ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                        "h-6 w-6 shrink-0 transition-colors"
                      )}
                      aria-hidden="true"
                    />
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </li>
          <li className="mt-auto">
            <Link
              href="/settings"
              className="group -mx-2 flex gap-x-3 rounded-md p-2 text-sm font-semibold leading-6 text-muted-foreground hover:bg-secondary/50 hover:text-foreground transition-colors"
            >
              <Settings
                className="h-6 w-6 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors"
                aria-hidden="true"
              />
              Settings
            </Link>
          </li>
        </ul>
      </nav>
    </div>
  );
}
