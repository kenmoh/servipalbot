"use client";

import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { 
  Search, 
  FileText, 
  Send, 
  Loader2,
  ChevronRight,
  Zap
} from "lucide-react";
import { useMemo, useState } from "react";

type DraftEmailOption = {
  id: string;
  email: string;
  subject: string;
  status: string;
};

interface ActionFormsProps {
  scrapeForm: {
    location: string;
    categories: string;
    maxLeads: string;
  };
  setScrapeForm: (form: any) => void;
  draftCount: string;
  setDraftCount: (count: string) => void;
  draftIds: string;
  setDraftIds: (ids: string) => void;
  draftEmailOptions: DraftEmailOption[];
  busy: string;
  queueScrape: () => Promise<void>;
  generateDrafts: () => Promise<void>;
  sendDrafts: () => Promise<void>;
}

export function ActionForms({
  scrapeForm,
  setScrapeForm,
  draftCount,
  setDraftCount,
  draftIds,
  setDraftIds,
  draftEmailOptions,
  busy,
  queueScrape,
  generateDrafts,
  sendDrafts
}: ActionFormsProps) {
  const [draftPicker, setDraftPicker] = useState("");
  const sendableEmailOptions = useMemo(
    () => draftEmailOptions.filter((item) => item.status === "draft" || item.status === "failed"),
    [draftEmailOptions]
  );

  const selectedDraftIds = useMemo(() => {
    return draftIds
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }, [draftIds]);

  function addDraftId(id: string) {
    const trimmed = id.trim();
    if (!trimmed) return;
    if (selectedDraftIds.includes(trimmed)) return;
    setDraftIds([...selectedDraftIds, trimmed].join(", "));
  }

  function removeDraftId(id: string) {
    setDraftIds(selectedDraftIds.filter((item) => item !== id).join(", "));
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {/* Lead Discovery Section */}
      <Card className="border-border bg-card overflow-hidden flex flex-col hover:border-primary/50 transition-colors">
        <CardHeader className="pb-4">
          <div className="p-2 rounded-lg bg-blue-400/10 w-fit mb-3 border border-blue-400/20">
            <Search className="h-4 w-4 text-blue-400" />
          </div>
          <CardTitle className="text-xl font-bold text-foreground">Lead Discovery</CardTitle>
          <CardDescription className="text-muted-foreground">Search for new prospects on Google Maps.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 flex-1">
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Location</label>
            <Input 
              className="bg-background border-border focus:ring-primary h-10" 
              value={scrapeForm.location}
              onChange={(e) => setScrapeForm({ ...scrapeForm, location: e.target.value })}
              placeholder="City, Country"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Categories</label>
            <Input 
              className="bg-background border-border focus:ring-primary h-10" 
              value={scrapeForm.categories}
              onChange={(e) => setScrapeForm({ ...scrapeForm, categories: e.target.value })}
              placeholder="restaurant, laundry..."
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Limit</label>
            <Input 
              className="bg-background border-border focus:ring-primary h-10" 
              type="number"
              value={scrapeForm.maxLeads}
              onChange={(e) => setScrapeForm({ ...scrapeForm, maxLeads: e.target.value })}
              placeholder="10"
            />
          </div>
          <Button 
            className="mt-auto bg-primary text-primary-foreground hover:bg-primary/90 h-10 w-full gap-2 transition-all active:scale-[0.98] font-bold" 
            onClick={queueScrape}
            disabled={busy === "scrape"}
          >
            {busy === "scrape" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {busy === "scrape" ? "Processing..." : "Start Discovery"}
          </Button>
        </CardContent>
      </Card>

      {/* Email Drafts Section */}
      <Card className="border-border bg-card overflow-hidden flex flex-col hover:border-amber-400/50 transition-colors">
        <CardHeader className="pb-4">
          <div className="p-2 rounded-lg bg-amber-400/10 w-fit mb-3 border border-amber-400/20">
            <FileText className="h-4 w-4 text-amber-400" />
          </div>
          <CardTitle className="text-xl font-bold text-foreground">Email Drafts</CardTitle>
          <CardDescription className="text-muted-foreground">Generate outreach content for new leads.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 flex-1">
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Max Drafts</label>
            <Input 
              className="bg-background border-border focus:ring-primary h-10" 
              type="number"
              value={draftCount}
              onChange={(e) => setDraftCount(e.target.value)}
              placeholder="5"
            />
          </div>
          <div className="flex-1 min-h-[40px]"></div>
          <Button 
            variant="secondary"
            className="mt-auto bg-secondary text-foreground hover:bg-secondary/80 h-10 w-full gap-2 transition-all active:scale-[0.98] font-bold" 
            onClick={generateDrafts}
            disabled={busy === "drafts"}
          >
            {busy === "drafts" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronRight className="h-4 w-4" />}
            {busy === "drafts" ? "Generating..." : "Generate Drafts"}
          </Button>
        </CardContent>
      </Card>

      {/* Outbound Dispatch Section */}
      <Card className="border-border bg-card overflow-hidden flex flex-col hover:border-emerald-400/50 transition-colors">
        <CardHeader className="pb-4">
          <div className="p-2 rounded-lg bg-emerald-400/10 w-fit mb-3 border border-emerald-400/20">
            <Send className="h-4 w-4 text-emerald-400" />
          </div>
          <CardTitle className="text-xl font-bold text-foreground">Outbound Dispatch</CardTitle>
          <CardDescription className="text-muted-foreground">Send finalized drafts to prospect inbox.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 flex-1">
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Draft Email Picker</label>
            <select
              value={draftPicker}
              onChange={(event) => {
                const selected = event.target.value;
                setDraftPicker("");
                if (!selected) return;
                addDraftId(selected);
              }}
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="" hidden>
                Select draft(s) to send
              </option>
              {draftEmailOptions.length === 0 ? (
                <option value="" disabled>
                  No draft emails found
                </option>
              ) : (
                sendableEmailOptions.map((draft) => (
                  <option key={draft.id} value={draft.id}>
                    [{draft.status}] {draft.email} | {draft.subject}
                  </option>
                ))
              )}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Email IDs</label>
            <Input 
              className="bg-background border-border focus:ring-primary h-10" 
              value={draftIds}
              onChange={(e) => setDraftIds(e.target.value)}
              placeholder="e.g. 101, 102, 103"
            />
            {selectedDraftIds.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {selectedDraftIds.map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => removeDraftId(id)}
                    className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/40 px-3 py-1 text-[11px] font-mono text-foreground/80 hover:bg-secondary/60"
                    title="Remove"
                  >
                    <span className="max-w-[240px] truncate">{id}</span>
                    <span className="text-muted-foreground">×</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="flex-1 min-h-[40px]"></div>
          <Button 
            className="mt-auto bg-foreground text-background hover:bg-foreground/90 h-10 w-full gap-2 transition-all active:scale-[0.98] font-bold" 
            onClick={sendDrafts}
            disabled={busy === "send"}
          >
            {busy === "send" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {busy === "send" ? "Sending..." : "Dispatch Emails"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
