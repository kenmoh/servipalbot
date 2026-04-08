"use client";

import { useEffect, useState } from "react";
import { StatsCards } from "@/components/stats-cards";
import { LeadsTable } from "@/components/leads-table";
import { LogList } from "@/components/log-list";
import { ActionForms } from "@/components/action-forms";
import { AlertCircle, RefreshCw, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";

type Readiness = {
  config?: Record<string, boolean>;
  services?: Record<string, Record<string, string | boolean | number>>;
};

type BotStatus = {
  last_run_status?: string;
  total_leads?: number;
  new_leads?: number;
  contacted_leads?: number;
  replied_leads?: number;
  messages_sent_today?: number;
  emails_sent_today?: number;
  posts_published_today?: number;
};

type Lead = {
  id: string;
  name: string;
  category?: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  source?: string;
  status?: string;
};

type EmailRecord = {
  id: string;
  email: string;
  subject: string;
  status: string;
  created_at?: string;
};

type LogRecord = {
  id: string;
  level: string;
  message: string;
  module: string;
  created_at?: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

const initialScrape = {
  location: "Lagos, Nigeria",
  categories: "restaurant,laundry,delivery",
  maxLeads: "12",
};

export default function Home() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [emails, setEmails] = useState<EmailRecord[]>([]);
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<string>("");
  const [scrapeForm, setScrapeForm] = useState(initialScrape);
  const [draftCount, setDraftCount] = useState("5");
  const [draftIds, setDraftIds] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed with ${response.status}`);
    }

    return response.json() as Promise<T>;
  }

  async function loadDashboard() {
    try {
      setRefreshing(true);
      setError("");
      const [readinessData, statusData, leadsData, emailsData, logsData] = await Promise.all([
        request<Readiness>("/system/readiness"),
        request<BotStatus>("/bot/status"),
        request<{ leads: Lead[] }>("/leads?limit=10"),
        request<{ emails: EmailRecord[] }>("/emails?limit=200"),
        request<{ logs: LogRecord[] }>("/logs?limit=8"),
      ]);

      setReadiness(readinessData);
      setBotStatus(statusData);
      setLeads(leadsData.leads || []);
      setEmails(emailsData.emails || []);
      setLogs(logsData.logs || []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function queueScrape() {
    try {
      setBusy("scrape");
      setError("");
      await request("/scrape/leads", {
        method: "POST",
        body: JSON.stringify({
          sources: ["google_maps"],
          location: scrapeForm.location,
          categories: scrapeForm.categories
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          max_leads: Number(scrapeForm.maxLeads),
        }),
      });
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to queue scrape");
    } finally {
      setBusy("");
    }
  }

  async function generateDrafts() {
    try {
      setBusy("drafts");
      setError("");
      await request("/outreach/email", {
        method: "POST",
        body: JSON.stringify({
          max_emails: Number(draftCount),
          dry_run: false,
        }),
      });
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to generate drafts");
    } finally {
      setBusy("");
    }
  }

  async function sendDrafts() {
    try {
      setBusy("send");
      setError("");
      const emailIds = draftIds
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      await request("/outreach/email/send", {
        method: "POST",
        body: JSON.stringify({ email_ids: emailIds }),
      });
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to send drafts");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-[1400px] mx-auto pb-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <LayoutDashboard className="h-6 w-6 text-primary" />
            Control Room
          </h1>
          <p className="text-muted-foreground text-xs mt-1 font-medium italic">Monitoring automation flow & lead generation</p>
        </div>
        <Button 
          variant="outline" 
          onClick={() => loadDashboard()}
          className="border-border bg-card hover:bg-secondary text-foreground text-xs h-9 gap-2 shadow-sm"
          disabled={refreshing}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Sync Data
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium animate-in fade-in slide-in-from-top-4">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}

      {/* Stats Section */}
      <StatsCards status={botStatus} />

      {/* Action Section */}
      <ActionForms 
        scrapeForm={scrapeForm}
        setScrapeForm={setScrapeForm}
        draftCount={draftCount}
        setDraftCount={setDraftCount}
        draftIds={draftIds}
        setDraftIds={setDraftIds}
        draftEmailOptions={emails.filter((email) => email.status === "draft")}
        busy={busy}
        queueScrape={queueScrape}
        generateDrafts={generateDrafts}
        sendDrafts={sendDrafts}
      />

      {/* Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <LeadsTable leads={leads} />
        </div>
        <div className="lg:col-span-1 h-full">
          <LogList logs={logs} onRefresh={() => loadDashboard()} />
        </div>
      </div>
    </div>
  );
}
