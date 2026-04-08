"use client";

import { 
  Users, 
  Mail, 
  Send, 
  CheckCircle2, 
  Activity,
  ArrowUpRight,
  TrendingUp
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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

interface StatsCardsProps {
  status: BotStatus | null;
}

export function StatsCards({ status }: StatsCardsProps) {
  const stats = [
    {
      name: "Total Leads",
      value: status?.total_leads || 0,
      icon: Users,
      color: "text-blue-400",
      bg: "bg-blue-400/10",
    },
    {
      name: "Emails Sent Today",
      value: status?.emails_sent_today || 0,
      icon: Send,
      color: "text-emerald-400",
      bg: "bg-emerald-400/10",
    },
    {
      name: "New Leads",
      value: status?.new_leads || 0,
      icon: TrendingUp,
      color: "text-amber-400",
      bg: "bg-amber-400/10",
    },
    {
      name: "Last Run Status",
      value: status?.last_run_status || "Idle",
      icon: Activity,
      color: "text-primary",
      bg: "bg-primary/10",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.name} className="overflow-hidden border-border bg-card hover:bg-accent/5 transition-all duration-300">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {stat.name}
            </CardTitle>
            <div className={`p-2 rounded-lg ${stat.bg} border border-${stat.color.split('-')[1]}-400/20`}>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{stat.value}</div>
            <p className="text-[10px] text-muted-foreground mt-1 flex items-center">
              <ArrowUpRight className="h-3 w-3 mr-1 text-emerald-400" />
              <span className="text-emerald-400 font-medium">+2.5%</span> 
              <span className="ml-1">since yesterday</span>
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
