"use client";

import {
  Badge
} from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import { Search, ExternalLink, Globe } from "lucide-react";
import { Input } from "@/components/ui/input";

export const LEAD_STATUSES = [
  "new",
  "contacted",
  "delivered",
  "read",
  "replied",
  "converted",
  "unsubscribed",
] as const;

type Lead = {
  id: string;
  name: string;
  category?: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  source?: string;
  status?: string;
  website?: string | null;
};

interface LeadsTableProps {
  leads: Lead[];
  /** When provided, renders functional search/filter controls bound to these values. */
  search?: string;
  onSearchChange?: (value: string) => void;
  statusFilter?: string;
  onStatusFilterChange?: (value: string) => void;
  categoryFilter?: string;
  onCategoryFilterChange?: (value: string) => void;
  /** Distinct categories for the category dropdown. */
  categories?: string[];
}

export function LeadsTable({
  leads,
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  categoryFilter,
  onCategoryFilterChange,
  categories,
}: LeadsTableProps) {
  const hasControls =
    typeof onSearchChange === "function" ||
    typeof onStatusFilterChange === "function" ||
    typeof onCategoryFilterChange === "function";

  return (
    <Card className="border-border bg-card overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-4 flex-wrap">
        <div>
          <CardTitle className="text-xl font-bold text-foreground">Recent Leads</CardTitle>
          <CardDescription className="text-muted-foreground text-xs">A list of the latest potential customers discovered.</CardDescription>
        </div>
        {hasControls && (
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
              <Input
                value={search ?? ""}
                onChange={(e) => onSearchChange?.(e.target.value)}
                placeholder="Search by email or phone..."
                className="h-9 w-56 pl-8 text-xs bg-background border-border focus:ring-primary"
              />
            </div>
            <select
              value={categoryFilter ?? ""}
              onChange={(e) => onCategoryFilterChange?.(e.target.value)}
              className="h-9 rounded-md border border-border bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              aria-label="Filter by category"
            >
              <option value="">All categories</option>
              {(categories ?? []).map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
            <select
              value={statusFilter ?? ""}
              onChange={(e) => onStatusFilterChange?.(e.target.value)}
              className="h-9 rounded-md border border-border bg-background px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              aria-label="Filter by status"
            >
              <option value="">All statuses</option>
              {LEAD_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </option>
              ))}
            </select>
          </div>
        )}
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-secondary/30 border-y border-border">
              <TableRow className="hover:bg-transparent">
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Name</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Category</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3 w-[200px]">Website</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Contact</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Status</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Source</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.length > 0 ? (
                leads.map((lead) => (
                  <TableRow key={lead.id} className="hover:bg-secondary/20 transition-colors border-b border-border/50 last:border-0">
                    <TableCell className="font-semibold text-foreground py-4 text-sm">{lead.name}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">{lead.category}</TableCell>
                    <TableCell>
                      {lead.website ? (
                        <a
                          href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 text-primary hover:underline text-xs group"
                        >
                          <Globe className="h-3 w-3 opacity-70 group-hover:opacity-100" />
                          Visit Site
                          <ExternalLink className="h-2 w-2 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground/30 text-[10px]">N/A</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {lead.email || lead.phone ? (
                        <div className="flex flex-col gap-0.5">
                          {lead.email && (
                            <span className="flex items-center gap-1 text-foreground/80 font-medium">
                              {lead.email}
                            </span>
                          )}
                          <span className="text-[10px] opacity-60">{lead.phone || lead.location}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground/30">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-tight ${
                          lead.status === 'contacted' ? 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20' :
                          lead.status === 'replied' ? 'bg-blue-400/10 text-blue-400 border-blue-400/20' :
                          lead.status === 'converted' ? 'bg-emerald-400/20 text-emerald-300 border-emerald-400/30' :
                          'bg-secondary text-muted-foreground border-border'
                        }`}
                      >
                        {lead.status || 'New'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-[10px] uppercase tracking-wide">
                      {(lead.source || '').replace('_', ' ') || '—'}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground italic text-sm">
                    No leads found. Start a scrape to gather more.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
