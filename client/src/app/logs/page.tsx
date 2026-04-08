"use client";

import { useEffect, useState } from "react";
import { LogList } from "@/components/log-list";
import { FileText, AlertCircle } from "lucide-react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

export default function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/logs?limit=500`, { cache: 'no-store' });
      if (!response.ok) throw new Error("Failed to fetch logs");
      const data = await response.json();
      setLogs(data.logs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="flex flex-col gap-6 max-w-[1400px] mx-auto pb-10">
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
          <FileText className="h-6 w-6 text-primary" />
          Activity Logs
        </h1>
        <p className="text-muted-foreground text-xs mt-1 font-medium italic">Live system execution history</p>
      </div>
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}
      <div className={loading ? "opacity-50 pointer-events-none" : ""}>
        <LogList logs={logs} onRefresh={fetchLogs} />
      </div>
    </div>
  );
}
