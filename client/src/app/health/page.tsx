"use client";

import { useEffect, useState } from "react";
import { Activity, AlertCircle, CheckCircle, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

type Readiness = {
  timestamp: string;
  config: Record<string, boolean>;
  services: Record<string, Record<string, any>>;
};

export default function HealthPage() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/system/readiness`, { cache: "no-store" });
      if (!response.ok) throw new Error("Failed to fetch health status");
      const data = await response.json();
      setReadiness(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading health");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="flex flex-col gap-6 max-w-[1000px] mx-auto pb-10">
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
          <Activity className="h-6 w-6 text-primary" />
          System Health
        </h1>
        <p className="text-muted-foreground text-xs mt-1 font-medium italic">Detailed breakdown of integrations and services</p>
      </div>

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}

      {loading && !readiness && <p className="text-muted-foreground text-sm">Loading health data...</p>}

      {readiness && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Services Status</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {Object.entries(readiness.services).map(([key, details]) => (
                <div key={key} className="flex flex-col p-3 rounded-lg border border-border/50 bg-secondary/10">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm capitalize">{key.replace("_", " ")}</span>
                    <Badge variant={details.configured ? "default" : "secondary"}>
                      {details.configured ? "Configured" : "Not Configured"}
                    </Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Reachable: {details.reachable ? <CheckCircle className="inline h-3 w-3 text-emerald-500 ml-1" /> : <XCircle className="inline h-3 w-3 text-red-500 ml-1" />}
                    {details.error && <p className="text-red-500 mt-1 truncate">{details.error}</p>}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Configurations</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {Object.entries(readiness.config).map(([key, active]) => (
                <div key={key} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-secondary/10">
                  <span className="font-medium text-sm capitalize">{key}</span>
                  <Badge variant={active ? "default" : "secondary"} className={active ? "bg-emerald-500 text-white hover:bg-emerald-600" : ""}>
                    {active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
