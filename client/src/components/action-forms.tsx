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
  busy,
  queueScrape,
  generateDrafts,
  sendDrafts
}: ActionFormsProps) {
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
            <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Email IDs</label>
            <Input 
              className="bg-background border-border focus:ring-primary h-10" 
              value={draftIds}
              onChange={(e) => setDraftIds(e.target.value)}
              placeholder="e.g. 101, 102, 103"
            />
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
