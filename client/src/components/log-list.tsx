"use client";

import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Terminal, Clock, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

type LogRecord = {
  id: string;
  level: string;
  message: string;
  module: string;
  created_at?: string;
};

interface LogListProps {
  logs: LogRecord[];
  onRefresh?: () => void;
}

export function LogList({ logs, onRefresh }: LogListProps) {
  return (
    <Card className="border-border bg-card overflow-hidden flex flex-col h-full">
      <CardHeader className="flex flex-row items-center justify-between pb-2 border-b border-border/50 bg-secondary/10">
        <div>
          <CardTitle className="text-lg font-bold text-foreground flex items-center gap-2">
            <Terminal className="h-4 w-4 text-primary" />
            System Logs
          </CardTitle>
          <CardDescription className="text-muted-foreground text-[10px]">Real-time bot activities.</CardDescription>
        </div>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={onRefresh}
          className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-secondary"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
        </Button>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-4 space-y-3 bg-background/50">
        {logs.length > 0 ? (
          logs.map((log) => (
            <div key={log.id} className="group p-3 rounded-md bg-secondary/20 border border-border/50 hover:border-primary/30 transition-all">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Badge 
                    variant="outline" 
                    className={`text-[9px] font-bold px-1.5 py-0 rounded border ${
                      log.level === 'error' ? 'border-red-500/50 text-red-400 bg-red-500/5' :
                      log.level === 'warn' ? 'border-amber-500/50 text-amber-400 bg-amber-500/5' :
                      'border-emerald-500/50 text-emerald-400 bg-emerald-500/5'
                    }`}
                  >
                    {log.level}
                  </Badge>
                  <span className="text-[9px] font-semibold text-muted-foreground/60 uppercase tracking-tight">{log.module}</span>
                </div>
                <div className="flex items-center gap-1 text-[9px] text-muted-foreground/40">
                  <Clock className="h-3 w-3" />
                  {log.created_at ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'now'}
                </div>
              </div>
              <p className="text-[11px] text-foreground/80 leading-relaxed font-mono tracking-tight">{log.message}</p>
            </div>
          ))
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground py-10 opacity-40">
            <Terminal className="h-8 w-8 mb-2" />
            <p className="text-xs italic">No recent logs.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
