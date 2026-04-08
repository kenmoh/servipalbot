"use client";

import { useEffect, useState } from "react";
import { Settings, AlertCircle, Save, CheckCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

export default function SettingsPage() {
  const [useSerpApi, setUseSerpApi] = useState(false);
  const [emailDelaySeconds, setEmailDelaySeconds] = useState("30");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{type: "error"|"success", text: string} | null>(null);

  const fetchSettings = async () => {
    setLoading(true);
    setStatusMsg(null);
    try {
      const response = await fetch(`${apiBase}/system/readiness`, { cache: "no-store" });
      if (!response.ok) throw new Error("Failed to fetch settings");
      const data = await response.json();
      setUseSerpApi(!!data.runtime?.use_serpapi);
      const delayValue = data.runtime?.email_delay_seconds;
      if (typeof delayValue === "number" && Number.isFinite(delayValue)) {
        setEmailDelaySeconds(String(delayValue));
      }
    } catch (err) {
      setStatusMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Error loading settings"
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    setStatusMsg(null);
    try {
      const response = await fetch(`${apiBase}/system/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          use_serpapi: useSerpApi,
          email_delay_seconds: Number(emailDelaySeconds),
        })
      });
      if (!response.ok) throw new Error("Failed to save settings");
      const saved = await response.json().catch(() => null);
      const delayPersisted = saved?.persisted?.email_delay_seconds;
      setStatusMsg({
        type: "success",
        text:
          delayPersisted === false
            ? "Settings updated, but delay could not be persisted (create Supabase table runtime_settings)."
            : "Settings saved successfully",
      });
    } catch (err) {
      setStatusMsg({
        type: "error",
        text: err instanceof Error ? err.message : "Error saving settings"
      });
      fetchSettings(); // Revert on failure
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-[1000px] mx-auto pb-10">
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
          <Settings className="h-6 w-6 text-primary" />
          Settings
        </h1>
        <p className="text-muted-foreground text-xs mt-1 font-medium italic">Configure ServiPal and API overrides</p>
      </div>

      {statusMsg && (
        <div className={`flex items-center gap-3 p-4 rounded-xl border text-sm font-medium ${statusMsg.type === 'error' ? 'bg-red-50 border-red-100 text-red-700' : 'bg-emerald-50 border-emerald-100 text-emerald-700'}`}>
          {statusMsg.type === 'error' ? <AlertCircle className="h-5 w-5 shrink-0" /> : <CheckCircle className="h-5 w-5 shrink-0" />}
          {statusMsg.text}
        </div>
      )}

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-lg">Lead Generation Tools</CardTitle>
          <CardDescription>Configure the scraping tools used by the bot to locate leads.</CardDescription>
        </CardHeader>
        <CardContent className={loading ? "opacity-50" : ""}>
          <div className="flex items-center justify-between p-4 rounded-lg border border-border/50 bg-secondary/10">
            <div>
              <p className="font-semibold text-foreground">Use SerpAPI</p>
              <p className="text-xs text-muted-foreground mt-1">If enabled, Google Maps scraper will use SerpAPI. Otherwise it attempts a direct scrape. (Requires restarting app locally to persist, ephemeral on Render).</p>
            </div>
            <button
              onClick={() => setUseSerpApi(!useSerpApi)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 ${useSerpApi ? "bg-emerald-500" : "bg-neutral-200 dark:bg-neutral-700"}`}
              role="switch"
              aria-checked={useSerpApi}
            >
              <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${useSerpApi ? "translate-x-5" : "translate-x-0"}`} />
            </button>
          </div>

          <div className="mt-6 flex justify-end">
            <Button onClick={saveSettings} disabled={saving || loading}>
              {saving ? "Saving..." : "Save Settings"}
              <Save className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-lg">Email Delivery</CardTitle>
          <CardDescription>Throttling options used when sending saved draft emails in bulk.</CardDescription>
        </CardHeader>
        <CardContent className={loading ? "opacity-50" : ""}>
          <div className="flex items-center justify-between gap-6 p-4 rounded-lg border border-border/50 bg-secondary/10">
            <div>
              <p className="font-semibold text-foreground">Delay Between Emails (seconds)</p>
              <p className="text-xs text-muted-foreground mt-1">Applies between draft sends to avoid provider rate limits.</p>
            </div>
            <div className="w-40">
              <Input
                inputMode="numeric"
                type="number"
                min={0}
                max={600}
                value={emailDelaySeconds}
                onChange={(event) => setEmailDelaySeconds(event.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
