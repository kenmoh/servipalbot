"use client";

import { useEffect, useState } from "react";
import { Mail, AlertCircle, CheckCircle2, Clock, XCircle, X } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

type EmailRecord = {
  id: string;
  email: string;
  subject: string;
  status: string;
  body?: string;
  created_at?: string;
};

export default function EmailsPage() {
  const [emails, setEmails] = useState<EmailRecord[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<EmailRecord | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState({ email: "", subject: "", body: "" });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchEmails = async () => {
    setLoading(true);
    try {
      setError("");
      const data = await request<{ emails: EmailRecord[] }>("/emails?limit=200");
      setEmails(data.emails || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading emails");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmails();
  }, []);

  useEffect(() => {
    if (!selectedEmail) return;
    setIsEditing(false);
    setSaveError("");
    setDraft({
      email: selectedEmail.email ?? "",
      subject: selectedEmail.subject ?? "",
      body: selectedEmail.body ?? "",
    });
  }, [selectedEmail]);

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    if (!apiBase) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");

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

  async function saveDraftEdits() {
    if (!selectedEmail) return;

    try {
      setSaving(true);
      setSaveError("");

      const payload = {
        email: draft.email.trim(),
        subject: draft.subject.trim(),
        body: draft.body,
      };

      const updated = await request<{ email: EmailRecord }>(`/emails/${selectedEmail.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      const updatedEmail = updated.email;
      setEmails((current) =>
        current.map((item) => (item.id === updatedEmail.id ? { ...item, ...updatedEmail } : item))
      );
      setSelectedEmail((current) => (current ? { ...current, ...updatedEmail } : current));
      setIsEditing(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Unable to save changes");
    } finally {
      setSaving(false);
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "sent":
      case "delivered":
        return <CheckCircle2 className="h-3 w-3" />;
      case "draft":
      case "pending":
        return <Clock className="h-3 w-3" />;
      case "failed":
        return <XCircle className="h-3 w-3" />;
      default:
        return null;
    }
  };

  const getBadgeStyle = (status: string) => {
    switch (status) {
      case "sent":
      case "delivered":
        return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-transparent hover:bg-emerald-500/25";
      case "draft":
      case "pending":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-transparent hover:bg-amber-500/25";
      case "failed":
        return "bg-red-500/15 text-red-600 dark:text-red-400 border-transparent hover:bg-red-500/25";
      default:
        return "bg-secondary text-muted-foreground border-transparent";
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-[1400px] mx-auto pb-10 relative">
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight flex items-center gap-2">
          <Mail className="h-6 w-6 text-primary" />
          Email Outreach
        </h1>
        <p className="text-muted-foreground text-xs mt-1 font-medium italic">Record of cold email outreach</p>
      </div>
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium">
          <AlertCircle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}
      <Card className="border-border bg-card overflow-hidden">
        <CardContent className="p-0">
          <div className={`overflow-x-auto ${loading ? "opacity-50" : ""}`}>
            <Table>
              <TableHeader className="bg-secondary/30 border-y border-border">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Recipient</TableHead>
                  <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Subject</TableHead>
                  <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Status</TableHead>
                  <TableHead className="text-right font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {emails.length > 0 ? (
                  emails.map((email) => (
                    <TableRow 
                      key={email.id} 
                      onClick={() => setSelectedEmail(email)}
                      className="hover:bg-secondary/50 cursor-pointer transition-colors border-b border-border/50 last:border-0"
                    >
                      <TableCell className="font-semibold text-foreground py-4 text-sm">{email.email}</TableCell>
                      <TableCell className="text-muted-foreground text-xs font-medium">{email.subject}</TableCell>
                      <TableCell>
                        <Badge className={`gap-1 rounded-full px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${getBadgeStyle(email.status)}`}>
                          {getStatusIcon(email.status)}
                          {email.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground text-[11px]">
                        {email.created_at ? new Date(email.created_at).toLocaleString() : "—"}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="h-32 text-center text-muted-foreground italic text-sm">
                      {loading ? "Loading emails..." : "No email records found."}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Side Drawer Overlay */}
      {selectedEmail && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div 
            className="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity" 
            onClick={() => setSelectedEmail(null)} 
          />
          <div className="relative w-full max-w-lg bg-card border-l border-border shadow-2xl flex flex-col h-full animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between p-5 border-b border-border bg-secondary/10">
              <h2 className="text-lg font-bold text-foreground">Email Details</h2>
              <Button variant="ghost" size="icon" onClick={() => setSelectedEmail(null)} className="rounded-full hover:bg-secondary">
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
              {saveError && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-medium">
                  <AlertCircle className="h-5 w-5 shrink-0" />
                  {saveError}
                </div>
              )}
              <div className="flex flex-col gap-1.5">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Recipient</h3>
                {isEditing ? (
                  <Input
                    type="email"
                    value={draft.email}
                    onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))}
                  />
                ) : (
                  <p className="text-sm font-medium text-foreground">{selectedEmail.email}</p>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Status</h3>
                <div>
                  <Badge className={`gap-1 inline-flex rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${getBadgeStyle(selectedEmail.status)}`}>
                    {getStatusIcon(selectedEmail.status)}
                    {selectedEmail.status}
                  </Badge>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Subject</h3>
                {isEditing ? (
                  <Input
                    value={draft.subject}
                    onChange={(event) => setDraft((current) => ({ ...current, subject: event.target.value }))}
                  />
                ) : (
                  <p className="text-base font-semibold text-foreground">{selectedEmail.subject}</p>
                )}
              </div>
              <div className="flex flex-col gap-2 mt-2">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">Message Body</h3>
                {isEditing ? (
                  <textarea
                    value={draft.body}
                    onChange={(event) => setDraft((current) => ({ ...current, body: event.target.value }))}
                    rows={10}
                    className="text-sm bg-secondary/30 p-5 rounded-xl whitespace-pre-wrap border border-border/50 text-foreground/90 leading-relaxed font-medium focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                ) : (
                  <div className="text-sm bg-secondary/30 p-5 rounded-xl whitespace-pre-wrap border border-border/50 text-foreground/90 leading-relaxed font-medium">
                    {selectedEmail.body || <span className="italic text-muted-foreground">No message body available.</span>}
                  </div>
                )}
              </div>
            </div>
            <div className="p-4 border-t border-border bg-secondary/10 flex justify-end gap-2">
              {selectedEmail.status === "draft" && !isEditing && (
                <Button variant="outline" onClick={() => setIsEditing(true)}>
                  Edit draft
                </Button>
              )}
              {selectedEmail.status === "draft" && isEditing && (
                <>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsEditing(false);
                      setSaveError("");
                      setDraft({
                        email: selectedEmail.email ?? "",
                        subject: selectedEmail.subject ?? "",
                        body: selectedEmail.body ?? "",
                      });
                    }}
                    disabled={saving}
                  >
                    Cancel
                  </Button>
                  <Button onClick={() => saveDraftEdits()} disabled={saving}>
                    {saving ? "Saving..." : "Save changes"}
                  </Button>
                </>
              )}
              <Button variant="outline" onClick={() => setSelectedEmail(null)} disabled={saving}>
                Close panel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
