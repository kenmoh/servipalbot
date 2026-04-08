"use client";

import { useEffect, useState } from "react";
import { Mail, AlertCircle, CheckCircle2, Clock, XCircle } from "lucide-react";
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

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

type EmailRecord = {
  id: string;
  email: string;
  subject: string;
  status: string;
  created_at?: string;
};

export default function EmailsPage() {
  const [emails, setEmails] = useState<EmailRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchEmails = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/emails?limit=200`, { cache: "no-store" });
      if (!response.ok) throw new Error("Failed to fetch emails");
      const data = await response.json();
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "sent":
      case "delivered":
        return <CheckCircle2 className="h-3 w-3 text-emerald-500" />;
      case "draft":
      case "pending":
        return <Clock className="h-3 w-3 text-amber-500" />;
      case "failed":
        return <XCircle className="h-3 w-3 text-red-500" />;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-[1400px] mx-auto pb-10">
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
                    <TableRow key={email.id} className="hover:bg-secondary/20 transition-colors border-b border-border/50 last:border-0">
                      <TableCell className="font-semibold text-foreground py-4 text-sm">{email.email}</TableCell>
                      <TableCell className="text-muted-foreground text-xs">{email.subject}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="gap-1 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-tight">
                          {getStatusIcon(email.status)}
                          {email.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground text-xs">
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
    </div>
  );
}
