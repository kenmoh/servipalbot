"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LeadsTable } from "@/components/leads-table";
import { Users, AlertCircle, RefreshCcw, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

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

const PAGE_SIZE = 200;

function getExportPhoneNumbers(leads: Lead[]) {
  const phoneNumbers = new Set<string>();

  for (const lead of leads) {
    let phone = (lead.phone || "").replace(/\D/g, "");
    if (phone.startsWith("234")) phone = phone.slice(3);
    if (phone.startsWith("+234")) phone = phone.slice(4);
    if (phone.startsWith("0")) phone = phone.slice(1);
    if (phone.length === 10) phoneNumbers.add(phone);
  }

  return Array.from(phoneNumbers);
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const exportPhones = () => {
    const phoneNumbers = getExportPhoneNumbers(leads);
    if (phoneNumbers.length === 0) return;

    const file = new Blob([`${phoneNumbers.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "phone-numbers.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const fetchLeads = useCallback(async (searchTerm: string, status: string, category: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("order", "desc");
      if (searchTerm.trim()) params.set("search", searchTerm.trim());
      if (status) params.set("status", status);
      if (category) params.set("category", category);

      const response = await fetch(`${apiBase}/leads?${params.toString()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Failed to fetch leads");
      const data = await response.json();
      setLeads(data.leads || []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading leads");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const response = await fetch(`${apiBase}/leads/categories`, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      setCategories(data.categories || []);
    } catch {
      // Non-critical: the category dropdown just stays empty.
    }
  }, []);

  // Initial load (newest first) + category options.
  useEffect(() => {
    fetchLeads("", "", "");
    fetchCategories();
  }, [fetchLeads, fetchCategories]);

  // Debounced refetch when search or filters change (skip mount: initial fetch covers it).
  const skipNextDebounce = useRef(true);
  useEffect(() => {
    if (skipNextDebounce.current) {
      skipNextDebounce.current = false;
      return;
    }
    const timer = setTimeout(() => {
      fetchLeads(search, statusFilter, categoryFilter);
    }, 350);
    return () => clearTimeout(timer);
  }, [search, statusFilter, categoryFilter, fetchLeads]);

  return (
    <div className="flex flex-col gap-6 max-w-350 mx-auto pb-10">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <Users className="h-6 w-6 text-primary" />
            Leads Database
          </h1>
          <p className="text-muted-foreground text-xs mt-1 font-medium italic">Complete list of generated leads, newest first</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={exportPhones}
            disabled={loading || getExportPhoneNumbers(leads).length === 0}
            className="border-border bg-card hover:bg-secondary text-foreground text-xs h-9 gap-2 shadow-sm"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => fetchLeads(search, statusFilter, categoryFilter)}
            disabled={loading}
            className="border-border bg-card hover:bg-secondary text-foreground text-xs h-9 gap-2 shadow-sm"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}
      <div className={loading ? "opacity-50 pointer-events-none" : ""}>
        <LeadsTable
          leads={leads}
          categories={categories}
          search={search}
          onSearchChange={setSearch}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          categoryFilter={categoryFilter}
          onCategoryFilterChange={setCategoryFilter}
        />
      </div>
    </div>
  );
}
