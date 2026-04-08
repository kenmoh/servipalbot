"use client";

import { useEffect, useState } from "react";
import { LeadsTable } from "@/components/leads-table";
import { Users, AlertCircle } from "lucide-react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

export default function LeadsPage() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchLeads() {
      try {
        const response = await fetch(`${apiBase}/leads?limit=200`, { cache: 'no-store' });
        if (!response.ok) throw new Error("Failed to fetch leads");
        const data = await response.json();
        setLeads(data.leads || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading leads");
      } finally {
        setLoading(false);
      }
    }
    fetchLeads();
  }, []);

  return (
    <div className="flex flex-col gap-6 max-w-[1400px] mx-auto pb-10">
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
          <Users className="h-6 w-6 text-primary" />
          Leads Database
        </h1>
        <p className="text-muted-foreground text-xs mt-1 font-medium italic">Complete list of generated leads</p>
      </div>
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}
      <div className={loading ? "opacity-50 pointer-events-none" : ""}>
        <LeadsTable leads={leads} />
      </div>
    </div>
  );
}
